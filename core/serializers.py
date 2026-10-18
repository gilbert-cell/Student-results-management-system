from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import datetime
from .student_accounts import create_student_user

from .models import (
    AcademicYear,
    AssessmentWeight,
    AuditLog,
    Enrollment,
    Result,
    ResultApproval,
    ResultCorrection,
    SchoolClass,
    Student,
    StudentSubjectRegistration,
    Subject,
    Teacher,
    Term,
    User,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'role', 'phone_number', 'is_active')


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ('id', 'actor_name', 'action', 'model_name', 'description', 'created_at')

    def get_actor_name(self, obj):
        if not obj.actor:
            return 'System'
        return obj.actor.get_full_name() or obj.actor.username


class UserManagementSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'role',
            'phone_number',
            'is_active',
            'password',
        )
        read_only_fields = ('id',)

    def create(self, validated_data):
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, **validated_data)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        elevated_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN)
        if actor and actor.role == User.Role.ADMIN:
            if self.instance and self.instance.role in elevated_roles:
                raise serializers.ValidationError('Administrators cannot modify administrator accounts.')
            if attrs.get('role', getattr(self.instance, 'role', None)) in elevated_roles:
                raise serializers.ValidationError({'role': 'Only a Super Admin may grant administrator access.'})
        if self.instance and 'is_active' in attrs and actor and actor.role != User.Role.SUPER_ADMIN:
            raise serializers.ValidationError({'is_active': 'Only a Super Admin may change account status.'})
        if (
            self.instance
            and actor
            and self.instance.pk == actor.pk
            and actor.role == User.Role.SUPER_ADMIN
            and (
                attrs.get('role', self.instance.role) != User.Role.SUPER_ADMIN
                or attrs.get('is_active', self.instance.is_active) is False
            )
        ):
            raise serializers.ValidationError('You cannot demote or disable your own Super Admin account.')
        if actor and actor.role == User.Role.SUPER_ADMIN and self.instance and self.instance.role == User.Role.SUPER_ADMIN:
            demoting = attrs.get('role', self.instance.role) != User.Role.SUPER_ADMIN
            disabling = attrs.get('is_active', self.instance.is_active) is False
            if (demoting or disabling) and User.objects.filter(role=User.Role.SUPER_ADMIN, is_active=True).count() <= 1:
                raise serializers.ValidationError('The last active Super Admin cannot be demoted or disabled.')
        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class StudentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    account_status = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = (
            'id',
            'user',
            'full_name',
            'account_status',
            'admission_number',
            'middle_name',
            'date_of_birth',
            'gender',
            'parent_name',
            'parent_phone',
            'current_class',
            'status',
            'created_at',
        )

    def get_full_name(self, obj):
        return ' '.join(value for value in (obj.user.first_name, obj.middle_name, obj.user.last_name) if value) or obj.user.username

    def get_account_status(self, obj):
        if not obj.user.is_active:
            return 'PENDING_ACTIVATION' if hasattr(obj.user, 'student_activation') else 'INACTIVE'
        if obj.user.must_change_password:
            return 'PASSWORD_CHANGE_REQUIRED'
        return 'ACTIVE'


class StudentRosterSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ('id', 'full_name', 'admission_number', 'current_class')

    def get_full_name(self, obj):
        return ' '.join(value for value in (obj.user.first_name, obj.middle_name, obj.user.last_name) if value) or obj.user.username


class StudentCreateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=150, write_only=True)
    last_name = serializers.CharField(max_length=150, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True, write_only=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, write_only=True)
    admission_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        validators=[UniqueValidator(queryset=Student.objects.all())],
    )

    class Meta:
        model = Student
        fields = (
            'first_name', 'last_name', 'email', 'phone_number',
            'admission_number', 'middle_name', 'date_of_birth', 'gender', 'parent_name', 'current_class',
        )

    @transaction.atomic
    def create(self, validated_data):
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email', '')
        phone_number = validated_data.pop('phone_number', '')
        user, credentials = create_student_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
        )
        if not validated_data.get('admission_number'):
            validated_data['admission_number'] = generate_admission_number()
        student = Student.objects.create(user=user, **validated_data)
        student.initial_credentials = credentials
        return student


def generate_admission_number():
    """Return the next school generated student ID for this calendar year."""
    prefix = f'STU-{timezone.now().year}-'
    existing = Student.objects.filter(admission_number__startswith=prefix).values_list('admission_number', flat=True)
    sequence = max((int(value[len(prefix):]) for value in existing if value[len(prefix):].isdigit()), default=0) + 1
    candidate = f'{prefix}{sequence:04d}'
    while Student.objects.filter(admission_number=candidate).exists():
        sequence += 1
        candidate = f'{prefix}{sequence:04d}'
    return candidate


class StudentProfileManagementSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='user.last_name', required=False, allow_blank=True)
    email = serializers.EmailField(source='user.email', required=False, allow_blank=True)
    phone_number = serializers.CharField(source='user.phone_number', max_length=20, required=False, allow_blank=True)

    class Meta:
        model = Student
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'admission_number', 'middle_name', 'date_of_birth', 'gender', 'parent_name', 'parent_phone', 'current_class', 'status')

    def update(self, instance, validated_data):
        user_fields = validated_data.pop('user', {})
        for field, value in user_fields.items():
            setattr(instance.user, field, value)
        if user_fields:
            instance.user.save(update_fields=list(user_fields))
        return super().update(instance, validated_data)


class TeacherSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = (
            'id',
            'user',
            'full_name',
            'employee_id',
            'department',
            'qualification',
            'phone_number',
            'created_at',
        )

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class TeacherCreateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=150, write_only=True, validators=[UniqueValidator(queryset=User.objects.all())])
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, write_only=True)
    last_name = serializers.CharField(max_length=150, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Teacher
        fields = (
            'username', 'password', 'first_name', 'last_name', 'email',
            'employee_id', 'department', 'qualification', 'phone_number',
        )

    @transaction.atomic
    def create(self, validated_data):
        user_fields = {
            key: validated_data.pop(key)
            for key in ('username', 'password', 'first_name', 'last_name', 'email')
            if key in validated_data
        }
        password = user_fields.pop('password')
        user = User.objects.create_user(password=password, role=User.Role.TEACHER, **user_fields)
        return Teacher.objects.create(user=user, **validated_data)


class TeacherProfileManagementSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='user.last_name', required=False, allow_blank=True)
    email = serializers.EmailField(source='user.email', required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = Teacher
        fields = ('first_name', 'last_name', 'email', 'password', 'employee_id', 'department', 'qualification', 'phone_number')

    def update(self, instance, validated_data):
        user_fields = validated_data.pop('user', {})
        password = validated_data.pop('password', None)
        for field, value in user_fields.items():
            setattr(instance.user, field, value)
        user_update_fields = list(user_fields)
        if password:
            instance.user.set_password(password)
            user_update_fields.append('password')
        if user_update_fields:
            instance.user.save(update_fields=user_update_fields)
        return super().update(instance, validated_data)


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ('id', 'name', 'start_date', 'end_date', 'is_active')

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError({'end_date': 'End date must be after the start date.'})
        return attrs


class TermSerializer(serializers.ModelSerializer):
    academic_year = AcademicYearSerializer(read_only=True)

    class Meta:
        model = Term
        fields = ('id', 'academic_year', 'name', 'start_date', 'end_date', 'is_active')


class TermWriteSerializer(serializers.ModelSerializer):
    academic_year_id = serializers.PrimaryKeyRelatedField(source='academic_year', queryset=AcademicYear.objects.all())

    class Meta:
        model = Term
        fields = ('academic_year_id', 'name', 'start_date', 'end_date', 'is_active')

    def validate(self, attrs):
        academic_year = attrs.get('academic_year', getattr(self.instance, 'academic_year', None))
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError({'end_date': 'End date must be after the start date.'})
        if academic_year and start_date and end_date and (
            start_date < academic_year.start_date or end_date > academic_year.end_date
        ):
            raise serializers.ValidationError('Term dates must fall within the academic year.')
        return attrs


class AssessmentWeightSerializer(serializers.ModelSerializer):
    subject_id = serializers.PrimaryKeyRelatedField(source='subject', queryset=Subject.objects.all())
    academic_year_id = serializers.PrimaryKeyRelatedField(source='academic_year', queryset=AcademicYear.objects.all())
    term_id = serializers.PrimaryKeyRelatedField(source='term', queryset=Term.objects.all())

    class Meta:
        model = AssessmentWeight
        fields = ('id', 'subject_id', 'academic_year_id', 'term_id', 'assessment_type', 'weight')
        read_only_fields = ('id',)

    def validate(self, attrs):
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        year = attrs.get('academic_year', getattr(self.instance, 'academic_year', None))
        term = attrs.get('term', getattr(self.instance, 'term', None))
        assessment_type = attrs.get('assessment_type', getattr(self.instance, 'assessment_type', ''))
        weight = attrs.get('weight', getattr(self.instance, 'weight', 0))
        if subject and year and term and AssessmentWeight.objects.filter(
            subject=subject, academic_year=year, term=term, assessment_type__iexact=assessment_type,
        ).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError({'assessment_type': 'This assessment type already has a weight for this subject and term.'})
        if year and term and term.academic_year_id != year.id:
            raise serializers.ValidationError({'term_id': 'The term must belong to the selected academic year.'})
        if subject and year and subject.school_class.academic_year_id != year.id:
            raise serializers.ValidationError({'subject_id': 'The subject class must belong to the selected academic year.'})
        existing = AssessmentWeight.objects.filter(subject=subject, academic_year=year, term=term)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        total = sum((row.weight for row in existing), weight * 0) + weight
        if total > 100:
            raise serializers.ValidationError({'weight': 'Assessment weights for a subject and term cannot total more than 100%.'})
        return attrs


class SchoolClassSerializer(serializers.ModelSerializer):
    teacher = serializers.SerializerMethodField()
    teacher_id = serializers.IntegerField(read_only=True, allow_null=True)
    academic_year = AcademicYearSerializer(read_only=True)

    class Meta:
        model = SchoolClass
        fields = ('id', 'name', 'section', 'academic_year', 'teacher', 'teacher_id', 'is_active', 'max_optional_subjects')

    def get_teacher(self, obj):
        if not obj.teacher:
            return None
        return obj.teacher.user.get_full_name() or obj.teacher.user.username


class SchoolClassWriteSerializer(serializers.ModelSerializer):
    academic_year_id = serializers.PrimaryKeyRelatedField(source='academic_year', queryset=AcademicYear.objects.all())
    teacher_id = serializers.PrimaryKeyRelatedField(
        source='teacher', queryset=Teacher.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = SchoolClass
        fields = ('name', 'section', 'academic_year_id', 'teacher_id', 'is_active', 'max_optional_subjects')

    def validate_max_optional_subjects(self, value):
        if value > 20:
            raise serializers.ValidationError('The optional subject limit cannot exceed 20.')
        return value


class SubjectSerializer(serializers.ModelSerializer):
    school_class = SchoolClassSerializer(read_only=True)
    teacher = serializers.SerializerMethodField()
    teacher_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Subject
        fields = ('id', 'code', 'name', 'school_class', 'teacher', 'teacher_id', 'description', 'is_optional')

    def get_teacher(self, obj):
        if not obj.teacher:
            return None
        return obj.teacher.user.get_full_name() or obj.teacher.user.username


class SubjectWriteSerializer(serializers.ModelSerializer):
    school_class_id = serializers.PrimaryKeyRelatedField(source='school_class', queryset=SchoolClass.objects.all())
    teacher_id = serializers.PrimaryKeyRelatedField(
        source='teacher', queryset=Teacher.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Subject
        fields = ('code', 'name', 'school_class_id', 'teacher_id', 'description', 'is_optional')


class EnrollmentSerializer(serializers.ModelSerializer):
    student = StudentRosterSerializer(read_only=True)
    school_class = SchoolClassSerializer(read_only=True)
    academic_year = AcademicYearSerializer(read_only=True)
    term = TermSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = ('id', 'student', 'school_class', 'academic_year', 'term', 'created_at')


class EnrollmentWriteSerializer(serializers.ModelSerializer):
    student_id = serializers.PrimaryKeyRelatedField(source='student', queryset=Student.objects.all())
    school_class_id = serializers.PrimaryKeyRelatedField(source='school_class', queryset=SchoolClass.objects.all())
    academic_year_id = serializers.PrimaryKeyRelatedField(source='academic_year', queryset=AcademicYear.objects.all())
    term_id = serializers.PrimaryKeyRelatedField(source='term', queryset=Term.objects.all())

    class Meta:
        model = Enrollment
        fields = ('student_id', 'school_class_id', 'academic_year_id', 'term_id')

    def validate(self, attrs):
        school_class = attrs.get('school_class')
        academic_year = attrs.get('academic_year')
        term = attrs.get('term')
        if school_class and academic_year and school_class.academic_year_id != academic_year.id:
            raise serializers.ValidationError({'academic_year_id': 'The class must belong to the selected academic year.'})
        if term and academic_year and term.academic_year_id != academic_year.id:
            raise serializers.ValidationError({'term_id': 'The term must belong to the selected academic year.'})
        return attrs


class ResultApprovalSerializer(serializers.ModelSerializer):
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ResultApproval
        fields = ('id', 'decision', 'comments', 'approved_by_name', 'created_at')

    def get_approved_by_name(self, obj):
        if not obj.approved_by:
            return 'System'
        return obj.approved_by.get_full_name() or obj.approved_by.username


class ResultSerializer(serializers.ModelSerializer):
    student = StudentRosterSerializer(read_only=True)
    subject = SubjectSerializer(read_only=True)
    academic_year = AcademicYearSerializer(read_only=True)
    term = TermSerializer(read_only=True)
    entered_by = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    approvals = ResultApprovalSerializer(many=True, read_only=True)

    class Meta:
        model = Result
        fields = (
            'id',
            'student',
            'subject',
            'academic_year',
            'term',
            'assessment_type',
            'marks',
            'grade',
            'remarks',
            'status',
            'entered_by',
            'approved_by',
            'approvals',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('grade', 'approved_by', 'created_at', 'updated_at')

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request and getattr(request.user, 'role', None) == User.Role.STUDENT:
            fields.pop('approvals', None)
            fields.pop('approved_by', None)
        return fields


class ResultWriteSerializer(serializers.ModelSerializer):
    student_id = serializers.PrimaryKeyRelatedField(
        source='student',
        queryset=Student.objects.all(),
        write_only=True,
    )
    subject_id = serializers.PrimaryKeyRelatedField(
        source='subject',
        queryset=Subject.objects.all(),
        write_only=True,
    )
    academic_year_id = serializers.PrimaryKeyRelatedField(
        source='academic_year',
        queryset=AcademicYear.objects.all(),
        write_only=True,
    )
    term_id = serializers.PrimaryKeyRelatedField(
        source='term',
        queryset=Term.objects.all(),
        write_only=True,
    )

    class Meta:
        model = Result
        fields = (
            'student_id',
            'subject_id',
            'academic_year_id',
            'term_id',
            'assessment_type',
            'marks',
            'remarks',
            'status',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        student = attrs.get('student', getattr(self.instance, 'student', None))
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        term = attrs.get('term', getattr(self.instance, 'term', None))
        academic_year = attrs.get('academic_year', getattr(self.instance, 'academic_year', None))

        if term and academic_year and term.academic_year_id != academic_year.id:
            raise serializers.ValidationError({'term_id': 'The term must belong to the selected academic year.'})
        if subject and academic_year and subject.school_class.academic_year_id != academic_year.id:
            raise serializers.ValidationError({'academic_year_id': 'The subject class must belong to the selected academic year.'})
        if student and subject and not Enrollment.objects.filter(
            student=student,
            school_class=subject.school_class,
            academic_year=academic_year,
            term=term,
        ).exists():
            raise serializers.ValidationError({'student_id': 'The student is not enrolled in this subject class for the selected term.'})
        if student and subject and subject.is_optional and not StudentSubjectRegistration.objects.filter(
            student=student, subject=subject, academic_year=academic_year, term=term,
        ).exists():
            raise serializers.ValidationError({'subject_id': 'The student has not registered for this optional subject.'})
        status_value = attrs.get('status')
        if status_value not in (None, Result.ResultStatus.DRAFT, Result.ResultStatus.SUBMITTED):
            raise serializers.ValidationError({'status': 'Results must be submitted for review before they can be approved or returned.'})
        return attrs


class BulkResultWriteSerializer(serializers.Serializer):
    subject_id = serializers.PrimaryKeyRelatedField(source='subject', queryset=Subject.objects.all())
    academic_year_id = serializers.PrimaryKeyRelatedField(source='academic_year', queryset=AcademicYear.objects.all())
    term_id = serializers.PrimaryKeyRelatedField(source='term', queryset=Term.objects.all())
    assessment_type = serializers.CharField(max_length=40)
    submit = serializers.BooleanField(required=False, default=False)
    rows = serializers.ListField(child=serializers.DictField(), min_length=1)

    def validate(self, attrs):
        term = attrs['term']
        academic_year = attrs['academic_year']
        subject = attrs['subject']
        if term.academic_year_id != academic_year.id:
            raise serializers.ValidationError({'term_id': 'Term must belong to the selected academic year.'})
        if subject.school_class.academic_year_id != academic_year.id:
            raise serializers.ValidationError({'subject_id': 'Subject class must belong to the selected academic year.'})
        cleaned = []
        for i, row in enumerate(attrs['rows']):
            try:
                student_id = int(row['student_id'])
                marks_raw = row.get('marks', '')
                if marks_raw == '' or marks_raw is None:
                    continue  # skip blank rows
                marks = float(marks_raw)
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError({'rows': f'Row {i+1}: student_id and numeric marks are required.'})
            if not (0 <= marks <= 100):
                raise serializers.ValidationError({'rows': f'Row {i+1}: marks must be between 0 and 100.'})
            try:
                student = Student.objects.get(pk=student_id)
            except Student.DoesNotExist:
                raise serializers.ValidationError({'rows': f'Row {i+1}: student not found.'})
            if not Enrollment.objects.filter(
                student=student, school_class=subject.school_class,
                academic_year=academic_year, term=term,
            ).exists():
                raise serializers.ValidationError({'rows': f'{student} is not enrolled in this class for the selected term.'})
            if subject.is_optional and not StudentSubjectRegistration.objects.filter(
                student=student, subject=subject, academic_year=academic_year, term=term,
            ).exists():
                raise serializers.ValidationError({'rows': f'{student} has not registered for optional subject {subject.name}.'})
            cleaned.append({'student': student, 'marks': marks, 'remarks': str(row.get('remarks', ''))})
        if not cleaned:
            raise serializers.ValidationError({'rows': 'Enter marks for at least one student.'})
        attrs['cleaned_rows'] = cleaned
        return attrs


class BulkApprovalSerializer(serializers.Serializer):
    result_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    action = serializers.ChoiceField(choices=('approve', 'return', 'publish'))
    comments = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        if attrs['action'] == 'return' and not attrs.get('comments', '').strip():
            raise serializers.ValidationError({'comments': 'A comment is required when returning results.'})
        return attrs


class BulkEnrollmentSerializer(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    school_class_id = serializers.PrimaryKeyRelatedField(source='school_class', queryset=SchoolClass.objects.all())
    academic_year_id = serializers.PrimaryKeyRelatedField(source='academic_year', queryset=AcademicYear.objects.all())
    term_id = serializers.PrimaryKeyRelatedField(source='term', queryset=Term.objects.all())

    def validate(self, attrs):
        school_class = attrs['school_class']
        academic_year = attrs['academic_year']
        term = attrs['term']
        if school_class.academic_year_id != academic_year.id:
            raise serializers.ValidationError({'school_class_id': 'The class must belong to the selected academic year.'})
        if term.academic_year_id != academic_year.id:
            raise serializers.ValidationError({'term_id': 'The term must belong to the selected academic year.'})
        students = list(Student.objects.filter(pk__in=attrs['student_ids']))
        if len(students) != len(attrs['student_ids']):
            raise serializers.ValidationError({'student_ids': 'One or more student IDs were not found.'})
        attrs['students'] = students
        return attrs


class BulkUserImportSerializer(serializers.Serializer):
    rows = serializers.ListField(child=serializers.DictField(), min_length=1)
    role = serializers.ChoiceField(choices=('STUDENT', 'TEACHER'))

    def validate(self, attrs):
        cleaned = []
        errors = []
        seen_usernames = set()
        seen_student_ids = set()
        for i, row in enumerate(attrs['rows']):
            first_name = str(row.get('first_name', '')).strip()
            last_name = str(row.get('last_name', '')).strip()
            email = str(row.get('email', '')).strip()
            if attrs['role'] == 'STUDENT':
                username = str(row.get('username', '')).strip()
                password = str(row.get('password', '')).strip()
                if not username:
                    errors.append(f'Row {i+1}: username is required.')
                    continue
                if not password or len(password) < 8:
                    errors.append(f'Row {i+1}: password must be at least 8 characters.')
                    continue
                if username in seen_usernames or User.objects.filter(username=username).exists():
                    errors.append(f'Row {i+1}: username "{username}" already exists.')
                    continue
                seen_usernames.add(username)
                entry = {'username': username, 'password': password, 'first_name': first_name, 'last_name': last_name, 'email': email}
                admission = str(row.get('admission_number', '')).strip()
                if admission and (admission in seen_student_ids or Student.objects.filter(admission_number=admission).exists()):
                    errors.append(f'Row {i+1}: admission number "{admission}" already exists.')
                    continue
                if admission:
                    seen_student_ids.add(admission)
                    entry['admission_number'] = admission
                entry['gender'] = str(row.get('gender', '')).strip()
                entry['parent_name'] = str(row.get('parent_name', '')).strip()
            else:
                emp_id = str(row.get('employee_id', '')).strip()
                if not emp_id:
                    errors.append(f'Row {i+1}: employee_id is required for teachers.')
                    continue
                username = emp_id
                if username in seen_usernames or User.objects.filter(username=username).exists() or Teacher.objects.filter(employee_id=emp_id).exists():
                    errors.append(f'Row {i+1}: employee_id "{emp_id}" already exists.')
                    continue
                seen_usernames.add(username)
                entry = {'username': username, 'first_name': first_name, 'last_name': last_name, 'email': email}
                entry['employee_id'] = emp_id
                entry['department'] = str(row.get('department', '')).strip()
                entry['qualification'] = str(row.get('qualification', '')).strip()
            cleaned.append(entry)
        if not cleaned:
            raise serializers.ValidationError({'rows': errors or ['No valid rows to import.']})
        attrs['cleaned_rows'] = cleaned
        attrs['row_errors'] = errors
        return attrs


class StudentRegistrationImportSerializer(serializers.Serializer):
    rows = serializers.ListField(child=serializers.DictField(), min_length=1, max_length=5000)
    academic_year_id = serializers.IntegerField(required=False)
    term_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        valid_rows = []
        row_errors = []
        duplicates = []
        seen_admissions = set()
        active_year = AcademicYear.objects.filter(is_active=True).order_by('-start_date').first()
        selected_year_id = attrs.get('academic_year_id', getattr(active_year, 'pk', None))
        import_year = AcademicYear.objects.filter(pk=selected_year_id).first() if selected_year_id else None
        if not import_year:
            raise serializers.ValidationError({'academic_year_id': 'Select a valid academic year.'})
        import_term = None
        if attrs.get('term_id'):
            import_term = Term.objects.filter(pk=attrs['term_id'], academic_year=import_year).first()
            if not import_term:
                raise serializers.ValidationError({'term_id': 'Select a term in the chosen academic year.'})
        else:
            import_term = Term.objects.filter(is_active=True, academic_year=import_year).select_related('academic_year').first()
        attrs['import_year'] = import_year
        attrs['import_term'] = import_term
        classes = list(SchoolClass.objects.filter(academic_year=import_year, is_active=True))
        aliases = {
            'admission_no': 'admission_number', 'student_id': 'admission_number',
            'first_name': 'first_name', 'middle_name': 'middle_name', 'last_name': 'last_name',
            'date_of_birth': 'date_of_birth', 'dob': 'date_of_birth', 'parent_phone': 'parent_phone',
            'phone': 'parent_phone', 'class': 'class_name', 'form_class': 'class_name',
        }
        for index, source in enumerate(attrs['rows'], start=2):
            row = {}
            for key, value in source.items():
                normalized = str(key).strip().lower().replace(' ', '_').replace('-', '_')
                row[aliases.get(normalized, normalized)] = str(value).strip() if value is not None else ''
            errors = []
            if not row.get('first_name'):
                errors.append('missing first_name')
            if not row.get('last_name'):
                errors.append('missing last_name')
            admission = row.get('admission_number', '')
            if len(admission) > 20:
                errors.append('admission_number cannot exceed 20 characters')
            if admission and (admission in seen_admissions or Student.objects.filter(admission_number=admission).exists()):
                duplicates.append(f'Row {index}: admission number {admission} already exists.')
                continue
            if admission:
                seen_admissions.add(admission)
            gender = row.get('gender', '').strip().title()
            if gender and gender not in ('Female', 'Male'):
                errors.append('invalid gender (use Female or Male)')
            birth_date = row.get('date_of_birth', '')
            parsed_birth_date = parse_date(birth_date) if birth_date else None
            if birth_date and not parsed_birth_date:
                for date_format in ('%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%m-%d-%Y'):
                    try:
                        parsed_birth_date = datetime.strptime(birth_date, date_format).date()
                        break
                    except ValueError:
                        continue
            email = row.get('email', '').strip()
            if email:
                try:
                    serializers.EmailField().run_validation(email)
                except serializers.ValidationError:
                    errors.append('invalid email')
            for field, maximum in (('first_name', 150), ('middle_name', 150), ('last_name', 150), ('parent_name', 120), ('parent_phone', 20)):
                if len(row.get(field, '')) > maximum:
                    errors.append(f'{field} cannot exceed {maximum} characters')
            class_name = row.get('class_name', '').strip()
            form_name = row.get('form', '').strip()
            school_class = None
            if class_name:
                school_class = next((item for item in classes if str(item).casefold() == class_name.casefold()), None)
                if school_class is None:
                    errors.append(f'class "{class_name}" not found in academic year {import_year.name}')
                elif import_term is None or import_term.academic_year_id != school_class.academic_year_id:
                    errors.append('select a term for the chosen class academic year')
            if len(class_name or form_name) > 80:
                errors.append('class_name cannot exceed 80 characters')
            if errors:
                row_errors.append(f'Row {index}: {", ".join(errors)}.')
                continue
            valid_rows.append({
                'admission_number': admission,
                'first_name': row['first_name'],
                'middle_name': row.get('middle_name', ''),
                'last_name': row['last_name'],
                'gender': gender,
                'date_of_birth': parsed_birth_date,
                'parent_name': row.get('parent_name', ''),
                'parent_phone': row.get('parent_phone', ''),
                'email': email,
                'current_class': str(school_class) if school_class else class_name or form_name,
                'school_class': school_class,
            })
        attrs.update(valid_rows=valid_rows, row_errors=row_errors, duplicates=duplicates)
        return attrs


class ResultReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(
        Result.ResultStatus.UNDER_REVIEW,
        Result.ResultStatus.APPROVED,
        Result.ResultStatus.RETURNED,
        Result.ResultStatus.PUBLISHED,
    ))
    comments = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        if attrs['status'] == Result.ResultStatus.RETURNED and not attrs.get('comments', '').strip():
            raise serializers.ValidationError({'comments': 'Add a comment explaining what needs to be corrected.'})
        return attrs


class ResultCorrectionSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    result_subject = serializers.SerializerMethodField()
    result_student = serializers.SerializerMethodField()

    class Meta:
        model = ResultCorrection
        fields = (
            'id', 'result', 'result_subject', 'result_student',
            'old_marks', 'new_marks', 'reason', 'status',
            'review_comment', 'requested_by_name', 'reviewed_by_name',
            'created_at', 'reviewed_at',
        )
        read_only_fields = ('id', 'old_marks', 'status', 'reviewed_by_name', 'reviewed_at', 'created_at')

    def get_requested_by_name(self, obj):
        if not obj.requested_by:
            return ''
        return obj.requested_by.get_full_name() or obj.requested_by.username

    def get_reviewed_by_name(self, obj):
        if not obj.reviewed_by:
            return ''
        return obj.reviewed_by.get_full_name() or obj.reviewed_by.username

    def get_result_subject(self, obj):
        return obj.result.subject.name

    def get_result_student(self, obj):
        return obj.result.student.user.get_full_name() or obj.result.student.admission_number


class ResultCorrectionRequestSerializer(serializers.Serializer):
    new_marks = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    reason = serializers.CharField(min_length=10, max_length=2000)


class ResultCorrectionReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=('approve', 'reject'))
    review_comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        if attrs['action'] == 'reject' and not attrs.get('review_comment', '').strip():
            raise serializers.ValidationError({'review_comment': 'A comment is required when rejecting a correction.'})
        return attrs


class PromotionPreviewSerializer(serializers.Serializer):
    source_class_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    academic_year_id = serializers.PrimaryKeyRelatedField(source='academic_year', queryset=AcademicYear.objects.all())
    term_id = serializers.PrimaryKeyRelatedField(source='term', queryset=Term.objects.all())
    pass_mark = serializers.DecimalField(max_digits=5, decimal_places=2, default=50, min_value=0, max_value=100)
