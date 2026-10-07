from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.db import transaction

from .models import (
    AcademicYear,
    AuditLog,
    Enrollment,
    Result,
    ResultApproval,
    SchoolClass,
    Student,
    Subject,
    Teacher,
    Term,
    User,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'role', 'phone_number')


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

    class Meta:
        model = Student
        fields = (
            'id',
            'user',
            'full_name',
            'admission_number',
            'date_of_birth',
            'gender',
            'parent_name',
            'current_class',
            'created_at',
        )

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class StudentRosterSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ('id', 'full_name', 'admission_number', 'current_class')

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class StudentCreateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=150, write_only=True, validators=[UniqueValidator(queryset=User.objects.all())])
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, write_only=True)
    last_name = serializers.CharField(max_length=150, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True, write_only=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Student
        fields = (
            'username', 'password', 'first_name', 'last_name', 'email', 'phone_number',
            'admission_number', 'date_of_birth', 'gender', 'parent_name', 'current_class',
        )

    @transaction.atomic
    def create(self, validated_data):
        user_fields = {
            key: validated_data.pop(key)
            for key in ('username', 'password', 'first_name', 'last_name', 'email', 'phone_number')
            if key in validated_data
        }
        password = user_fields.pop('password')
        user = User.objects.create_user(
            password=password,
            role=User.Role.STUDENT,
            **user_fields,
        )
        return Student.objects.create(user=user, **validated_data)


class StudentProfileManagementSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='user.last_name', required=False, allow_blank=True)
    email = serializers.EmailField(source='user.email', required=False, allow_blank=True)
    phone_number = serializers.CharField(source='user.phone_number', max_length=20, required=False, allow_blank=True)

    class Meta:
        model = Student
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'admission_number', 'date_of_birth', 'gender', 'parent_name', 'current_class')

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


class SchoolClassSerializer(serializers.ModelSerializer):
    teacher = serializers.SerializerMethodField()
    teacher_id = serializers.IntegerField(read_only=True, allow_null=True)
    academic_year = AcademicYearSerializer(read_only=True)

    class Meta:
        model = SchoolClass
        fields = ('id', 'name', 'section', 'academic_year', 'teacher', 'teacher_id', 'is_active')

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
        fields = ('name', 'section', 'academic_year_id', 'teacher_id', 'is_active')


class SubjectSerializer(serializers.ModelSerializer):
    school_class = SchoolClassSerializer(read_only=True)
    teacher = serializers.SerializerMethodField()
    teacher_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Subject
        fields = ('id', 'code', 'name', 'school_class', 'teacher', 'teacher_id', 'description')

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
        fields = ('code', 'name', 'school_class_id', 'teacher_id', 'description')


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
        status_value = attrs.get('status')
        if status_value not in (None, Result.ResultStatus.DRAFT, Result.ResultStatus.SUBMITTED):
            raise serializers.ValidationError({'status': 'Results must be submitted for review before they can be approved or returned.'})
        return attrs


class BulkResultWriteSerializer(serializers.Serializer):
    subject_id = serializers.PrimaryKeyRelatedField(source='subject', queryset=Subject.objects.all())
    academic_year_id = serializers.PrimaryKeyRelatedField(source='academic_year', queryset=AcademicYear.objects.all())
    term_id = serializers.PrimaryKeyRelatedField(source='term', queryset=Term.objects.all())
    assessment_type = serializers.CharField(max_length=40)
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
        for i, row in enumerate(attrs['rows']):
            username = str(row.get('username', '')).strip()
            password = str(row.get('password', '')).strip()
            first_name = str(row.get('first_name', '')).strip()
            last_name = str(row.get('last_name', '')).strip()
            if not username:
                errors.append(f'Row {i+1}: username is required.')
                continue
            if not password or len(password) < 8:
                errors.append(f'Row {i+1}: password must be at least 8 characters.')
                continue
            if User.objects.filter(username=username).exists():
                errors.append(f'Row {i+1}: username "{username}" already exists.')
                continue
            entry = {'username': username, 'password': password, 'first_name': first_name, 'last_name': last_name,
                     'email': str(row.get('email', '')).strip()}
            if attrs['role'] == 'STUDENT':
                admission = str(row.get('admission_number', '')).strip()
                if not admission:
                    errors.append(f'Row {i+1}: admission_number is required for students.')
                    continue
                entry['admission_number'] = admission
                entry['gender'] = str(row.get('gender', '')).strip()
                entry['parent_name'] = str(row.get('parent_name', '')).strip()
            else:
                emp_id = str(row.get('employee_id', '')).strip()
                if not emp_id:
                    errors.append(f'Row {i+1}: employee_id is required for teachers.')
                    continue
                entry['employee_id'] = emp_id
                entry['department'] = str(row.get('department', '')).strip()
                entry['qualification'] = str(row.get('qualification', '')).strip()
            cleaned.append(entry)
        if errors:
            raise serializers.ValidationError({'rows': errors})
        if not cleaned:
            raise serializers.ValidationError({'rows': 'No valid rows to import.'})
        attrs['cleaned_rows'] = cleaned
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
