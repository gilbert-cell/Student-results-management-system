from collections.abc import Mapping

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

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
from .permissions import (
    IsAdmin,
    IsAdminOrAcademicOfficer,
    IsAcademicManagerOrTeacher,
    IsAcademicManagerTeacherOrStudent,
    IsAnySystemRole,
    IsPublisher,
    IsResultEditor,
    IsResultReader,
    IsReviewer,
)

ADMIN_ROLES = (User.Role.SUPER_ADMIN, User.Role.ADMIN)
from .serializers import (
    AcademicYearSerializer,
    AuditLogSerializer,
    BulkApprovalSerializer,
    BulkEnrollmentSerializer,
    BulkResultWriteSerializer,
    BulkUserImportSerializer,
    EnrollmentWriteSerializer,
    EnrollmentSerializer,
    ResultSerializer,
    ResultReviewSerializer,
    ResultWriteSerializer,
    StudentCreateSerializer,
    StudentProfileManagementSerializer,
    SchoolClassSerializer,
    StudentRosterSerializer,
    SchoolClassWriteSerializer,
    StudentSerializer,
    TeacherCreateSerializer,
    TeacherProfileManagementSerializer,
    SubjectSerializer,
    SubjectWriteSerializer,
    TeacherSerializer,
    TermSerializer,
    TermWriteSerializer,
    UserManagementSerializer,
)


@api_view(['GET'])
@permission_classes([IsAnySystemRole])
def dashboard_summary(request):
    role = request.user.role
    active_year = AcademicYear.objects.filter(is_active=True).order_by('-start_date').first()
    active_term = None
    if active_year:
        active_term = Term.objects.filter(academic_year=active_year, is_active=True).order_by('start_date').first()
    students = Student.objects.all()
    teachers = Teacher.objects.all()
    classes = SchoolClass.objects.all()
    subjects = Subject.objects.all()
    result_set = Result.objects.all()
    top_result_filter = Q(results__status=Result.ResultStatus.PUBLISHED)
    if active_year and active_term:
        top_result_filter &= Q(results__academic_year=active_year, results__term=active_term)
    else:
        top_result_filter &= Q(results__pk__isnull=True)

    if role == User.Role.TEACHER:
        subjects = subjects.filter(teacher__user=request.user)
        classes = classes.filter(
            Q(teacher__user=request.user) | Q(subjects__teacher__user=request.user),
        ).distinct()
        students = students.filter(
            Q(enrollments__school_class__teacher__user=request.user)
            | Q(enrollments__school_class__subjects__teacher__user=request.user),
        ).distinct()
        teachers = teachers.filter(user=request.user)
        result_set = result_set.filter(
            Q(subject__teacher__user=request.user)
            | Q(subject__school_class__teacher__user=request.user),
        ).distinct()
        top_result_filter &= (
            Q(results__subject__teacher__user=request.user)
            | Q(results__subject__school_class__teacher__user=request.user)
        )
    elif role == User.Role.STUDENT:
        students = students.filter(user=request.user)
        teachers = Teacher.objects.none()
        classes = SchoolClass.objects.none()
        subjects = Subject.objects.none()
        result_set = result_set.filter(student__user=request.user, status=Result.ResultStatus.PUBLISHED)
        top_result_filter &= Q(results__student__user=request.user)

    approved_results = result_set.filter(status__in=[Result.ResultStatus.APPROVED, Result.ResultStatus.PUBLISHED]).count()
    current_term_results = result_set
    if active_year and active_term:
        current_term_results = current_term_results.filter(academic_year=active_year, term=active_term)
    else:
        current_term_results = current_term_results.none()
    published_results = current_term_results.filter(status=Result.ResultStatus.PUBLISHED)
    pending_results = current_term_results.filter(status__in=[
        Result.ResultStatus.DRAFT,
        Result.ResultStatus.SUBMITTED,
        Result.ResultStatus.UNDER_REVIEW,
    ]).count()
    average_performance = published_results.aggregate(average=Avg('marks'))['average']
    recent_results = result_set.select_related(
        'student__user', 'subject', 'term', 'academic_year', 'entered_by', 'approved_by'
    ).prefetch_related('approvals__approved_by').order_by('-updated_at')[:6]
    top_students = students.annotate(
        avg_marks=Avg('results__marks', filter=top_result_filter)
    ).filter(avg_marks__isnull=False).select_related('user').order_by('-avg_marks')[:5]
    status_counts = current_term_results.values('status').annotate(total=Count('id'))
    status_totals = {row['status']: row['total'] for row in status_counts}
    notifications = []

    def add_notification(title, message, count, section='Results', status_filter=''):
        if count:
            notifications.append({
                'title': title,
                'message': message,
                'count': count,
                'section': section,
                'status_filter': status_filter,
            })

    if role == User.Role.TEACHER:
        add_notification('Results returned for correction', 'Review the feedback and update returned marks.', status_totals.get(Result.ResultStatus.RETURNED, 0), status_filter='RETURNED')
        add_notification('Draft results to submit', 'Finish entering marks and submit them for review.', status_totals.get(Result.ResultStatus.DRAFT, 0), status_filter='DRAFT')
        add_notification('Submitted results in review', 'Your submitted results are being reviewed.', status_totals.get(Result.ResultStatus.SUBMITTED, 0) + status_totals.get(Result.ResultStatus.UNDER_REVIEW, 0), status_filter='REVIEW_QUEUE')
    elif role == User.Role.ACADEMIC_OFFICER:
        add_notification('Results awaiting review', 'Review submitted results and approve or return them.', status_totals.get(Result.ResultStatus.SUBMITTED, 0) + status_totals.get(Result.ResultStatus.UNDER_REVIEW, 0), status_filter='REVIEW_QUEUE')
    elif role in ADMIN_ROLES:
        add_notification('Approved results ready to publish', 'Publish approved results so students can view them.', status_totals.get(Result.ResultStatus.APPROVED, 0), status_filter='APPROVED')
        add_notification('Results awaiting review', 'Open the review queue to check submitted results.', status_totals.get(Result.ResultStatus.SUBMITTED, 0) + status_totals.get(Result.ResultStatus.UNDER_REVIEW, 0), status_filter='REVIEW_QUEUE')
    elif role == User.Role.STUDENT:
        add_notification('New results published', 'Your published results are ready to view.', status_totals.get(Result.ResultStatus.PUBLISHED, 0), section='My Results', status_filter='PUBLISHED')
    if role in ADMIN_ROLES:
        add_notification('Returned results need attention', 'Coordinate corrections with the responsible teachers.', status_totals.get(Result.ResultStatus.RETURNED, 0), status_filter='RETURNED')

    return Response({
        'school_name': getattr(settings, 'SCHOOL_NAME', ''),
        'stats': {
            'students': students.count(),
            'teachers': teachers.count(),
            'classes': classes.count(),
            'subjects': subjects.count(),
            'approved_results': approved_results,
            'pending_results': pending_results,
            'published_results': published_results.count(),
            'average_performance': round(float(average_performance), 1) if average_performance is not None else None,
        },
        'academic_context': {
            'academic_year': active_year.name if active_year else None,
            'term': active_term.name if active_term else None,
        },
        'result_status': {row['status'].lower(): row['total'] for row in status_counts},
        'notifications': notifications,
        'recent_results': ResultSerializer(recent_results, many=True, context={'request': request}).data,
        'top_students': [
            {
                'name': student.user.get_full_name() or student.user.username,
                'average': round(float(student.avg_marks or 0), 2),
                'admission_number': student.admission_number,
            }
            for student in top_students
        ],
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAnySystemRole])
def academic_years(request):
    if request.method == 'GET':
        years = AcademicYear.objects.all().order_by('-start_date')
        return Response(AcademicYearSerializer(years, many=True).data)
    if request.user.role not in ADMIN_ROLES:
        return Response({'detail': 'Only administrators may manage academic years.'}, status=status.HTTP_403_FORBIDDEN)
    serializer = AcademicYearSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            list(AcademicYear.objects.select_for_update().values_list('pk', flat=True))
            year = serializer.save()
            if year.is_active:
                AcademicYear.objects.exclude(pk=year.pk).filter(is_active=True).update(is_active=False)
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='AcademicYear',
                description=f'Created academic year {year.name} ({year.pk}).',
            )
        return Response(AcademicYearSerializer(year).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAdmin])
def manage_academic_year(request, year_id):
    with transaction.atomic():
        list(AcademicYear.objects.select_for_update().values_list('pk', flat=True))
        try:
            year = AcademicYear.objects.get(pk=year_id)
        except AcademicYear.DoesNotExist:
            return Response({'detail': 'Academic year not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AcademicYearSerializer(year, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        year = serializer.save()
        if year.is_active:
            AcademicYear.objects.exclude(pk=year.pk).filter(is_active=True).update(is_active=False)
        changed_fields = ', '.join(sorted(request.data.keys())) or 'academic year details'
        AuditLog.objects.create(
            actor=request.user,
            action='UPDATE',
            model_name='AcademicYear',
            description=f'Updated academic year {year.name} ({year.pk}); fields: {changed_fields}.',
        )
    return Response(AcademicYearSerializer(year).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAnySystemRole])
def terms(request):
    if request.method == 'GET':
        terms_queryset = Term.objects.select_related('academic_year').order_by('academic_year__start_date', 'start_date')
        year_id = request.query_params.get('academic_year_id')
        if year_id:
            if not year_id.isdecimal():
                return Response({'detail': 'Academic year ID must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)
            terms_queryset = terms_queryset.filter(academic_year_id=int(year_id))
        return Response(TermSerializer(terms_queryset, many=True).data)
    if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.ACADEMIC_OFFICER):
        return Response({'detail': 'This role may view but not manage terms.'}, status=status.HTTP_403_FORBIDDEN)
    serializer = TermWriteSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            term = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='Term',
                description=f'Created term {term.name} for academic year {term.academic_year.name} ({term.pk}).',
            )
        return Response(TermSerializer(term).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAdminOrAcademicOfficer])
def manage_term(request, term_id):
    try:
        term = Term.objects.select_related('academic_year').get(pk=term_id)
    except Term.DoesNotExist:
        return Response({'detail': 'Term not found.'}, status=status.HTTP_404_NOT_FOUND)
    requested_year_id = request.data.get('academic_year_id')
    if requested_year_id is not None and str(requested_year_id) != str(term.academic_year_id):
        return Response(
            {'academic_year_id': 'A term cannot be moved to a different academic year.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    serializer = TermWriteSerializer(term, data=request.data, partial=True)
    if serializer.is_valid():
        with transaction.atomic():
            term = serializer.save()
            changed_fields = ', '.join(sorted(request.data.keys())) or 'term details'
            AuditLog.objects.create(
                actor=request.user,
                action='UPDATE',
                model_name='Term',
                description=f'Updated term {term.name} for academic year {term.academic_year.name} ({term.pk}); fields: {changed_fields}.',
            )
        return Response(TermSerializer(term).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAnySystemRole])
def students(request):
    if request.method == 'GET':
        students = Student.objects.select_related('user').all().order_by('admission_number')
        if request.user.role == User.Role.TEACHER:
            students = students.filter(
                Q(enrollments__school_class__teacher__user=request.user)
                | Q(enrollments__school_class__subjects__teacher__user=request.user),
            ).distinct()
        elif request.user.role == User.Role.STUDENT:
            students = students.filter(user=request.user)
        class_id = request.query_params.get('class_id')
        if class_id:
            if not class_id.isdecimal():
                return Response({'detail': 'Class ID must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)
            students = students.filter(enrollments__school_class_id=int(class_id))
        query = request.query_params.get('q', '').strip()
        if query:
            students = students.filter(
                Q(admission_number__icontains=query)
                | Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__username__icontains=query)
            )
        serializer_class = StudentSerializer if request.user.role in (*ADMIN_ROLES, User.Role.ACADEMIC_OFFICER, User.Role.STUDENT) else StudentRosterSerializer
        return Response(serializer_class(students, many=True).data)

    if request.user.role not in ADMIN_ROLES:
        return Response({'detail': 'Only administrators may create student accounts.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = StudentCreateSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            student = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='Student',
                description=f'Created student {student.admission_number} ({student.pk}).',
            )
        return Response(StudentSerializer(student).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAdmin])
def manage_student(request, student_id):
    try:
        student = Student.objects.select_related('user').get(pk=student_id)
    except Student.DoesNotExist:
        return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = StudentProfileManagementSerializer(student, data=request.data, partial=True)
    if serializer.is_valid():
        with transaction.atomic():
            student = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='UPDATE',
                model_name='Student',
                description=f'Updated student {student.admission_number} ({student.pk}); fields: {", ".join(sorted(request.data.keys()))}.',
            )
        return Response(StudentSerializer(student).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAdminOrAcademicOfficer])
def teachers(request):
    if request.method == 'GET':
        teachers = Teacher.objects.select_related('user').all().order_by('employee_id')
        return Response(TeacherSerializer(teachers, many=True).data)

    if request.user.role not in ADMIN_ROLES:
        return Response({'detail': 'Only administrators may create teacher accounts.'}, status=status.HTTP_403_FORBIDDEN)
    serializer = TeacherCreateSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            teacher = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='Teacher',
                description=f'Created teacher {teacher.employee_id} ({teacher.pk}).',
            )
        return Response(TeacherSerializer(teacher).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAdmin])
def manage_teacher(request, teacher_id):
    try:
        teacher = Teacher.objects.select_related('user').get(pk=teacher_id)
    except Teacher.DoesNotExist:
        return Response({'detail': 'Teacher not found.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = TeacherProfileManagementSerializer(teacher, data=request.data, partial=True)
    if serializer.is_valid():
        with transaction.atomic():
            teacher = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='UPDATE',
                model_name='Teacher',
                description=f'Updated teacher {teacher.employee_id} ({teacher.pk}); fields: {", ".join(sorted(set(request.data.keys()) - {"password"}))}.',
            )
        return Response(TeacherSerializer(teacher).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAcademicManagerOrTeacher])
def school_classes(request):
    if request.method == 'GET':
        classes = SchoolClass.objects.select_related('academic_year', 'teacher__user').all().order_by('name')
        if request.user.role == User.Role.TEACHER:
            classes = classes.filter(Q(teacher__user=request.user) | Q(subjects__teacher__user=request.user)).distinct()
        return Response(SchoolClassSerializer(classes, many=True).data)

    if request.user.role == User.Role.TEACHER:
        return Response({'detail': 'Teachers may view only assigned classes.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = SchoolClassWriteSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            school_class = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='SchoolClass',
                description=f'Created class {school_class} ({school_class.pk}).',
            )
        return Response(SchoolClassSerializer(school_class).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAcademicManagerOrTeacher])
def manage_school_class(request, class_id):
    if request.user.role == User.Role.TEACHER:
        return Response({'detail': 'Teachers may view assigned classes but may not edit them.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        school_class = SchoolClass.objects.get(pk=class_id)
    except SchoolClass.DoesNotExist:
        return Response({'detail': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)
    requested_year_id = request.data.get('academic_year_id')
    if requested_year_id is not None and str(requested_year_id) != str(school_class.academic_year_id):
        return Response({'academic_year_id': 'A class cannot be moved to a different academic year.'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = SchoolClassWriteSerializer(school_class, data=request.data, partial=True)
    if serializer.is_valid():
        with transaction.atomic():
            school_class = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='UPDATE',
                model_name='SchoolClass',
                description=f'Updated class {school_class} ({school_class.pk}); fields: {", ".join(sorted(request.data.keys()))}.',
            )
        return Response(SchoolClassSerializer(school_class).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAcademicManagerTeacherOrStudent])
def subjects(request):
    if request.method == 'GET':
        subjects = Subject.objects.select_related('school_class', 'teacher__user').all().order_by('code')
        if request.user.role == User.Role.TEACHER:
            subjects = subjects.filter(teacher__user=request.user)
        elif request.user.role == User.Role.STUDENT:
            subjects = subjects.filter(school_class__enrollments__student__user=request.user).distinct()
        return Response(SubjectSerializer(subjects, many=True).data)

    if request.user.role == User.Role.TEACHER or request.user.role == User.Role.STUDENT:
        return Response({'detail': 'This role may view subjects but may not manage them.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = SubjectWriteSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            subject = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='Subject',
                description=f'Created subject {subject.code} ({subject.pk}).',
            )
        return Response(SubjectSerializer(subject).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAnySystemRole])
def manage_subject(request, subject_id):
    if request.user.role in (User.Role.TEACHER, User.Role.STUDENT):
        return Response({'detail': 'This role may view subjects but may not edit them.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        subject = Subject.objects.get(pk=subject_id)
    except Subject.DoesNotExist:
        return Response({'detail': 'Subject not found.'}, status=status.HTTP_404_NOT_FOUND)
    requested_class_id = request.data.get('school_class_id')
    if requested_class_id is not None and str(requested_class_id) != str(subject.school_class_id) and subject.results.exists():
        return Response({'school_class_id': 'A subject with recorded results cannot be moved to a different class.'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = SubjectWriteSerializer(subject, data=request.data, partial=True)
    if serializer.is_valid():
        with transaction.atomic():
            subject = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='UPDATE',
                model_name='Subject',
                description=f'Updated subject {subject.code} ({subject.pk}); fields: {", ".join(sorted(request.data.keys()))}.',
            )
        return Response(SubjectSerializer(subject).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAnySystemRole])
def enrollments(request):
    if request.method == 'GET':
        enrollments = Enrollment.objects.select_related('student__user', 'school_class', 'academic_year', 'term').all()
        if request.user.role == User.Role.TEACHER:
            enrollments = enrollments.filter(
                Q(school_class__teacher__user=request.user)
                | Q(school_class__subjects__teacher__user=request.user),
            ).distinct()
        elif request.user.role == User.Role.STUDENT:
            enrollments = enrollments.filter(student__user=request.user)
        return Response(EnrollmentSerializer(enrollments, many=True).data)

    if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.ACADEMIC_OFFICER):
        return Response({'detail': 'This role may view but not manage enrollments.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = EnrollmentWriteSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            enrollment = serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='Enrollment',
                description=(
                    f'Enrolled student {enrollment.student.admission_number} in '
                    f'{enrollment.school_class.name} for {enrollment.term.name} '
                    f'({enrollment.academic_year.name}).'
                ),
            )
        return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsResultEditor])
def bulk_create_results(request):
    """Create or update draft results for all students in one subject/term/assessment."""
    if request.user.role not in (*ADMIN_ROLES, User.Role.TEACHER):
        return Response({'detail': 'Only teachers may enter results.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = BulkResultWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    subject = serializer.validated_data['subject']
    academic_year = serializer.validated_data['academic_year']
    term = serializer.validated_data['term']
    assessment_type = serializer.validated_data['assessment_type']
    submit = request.data.get('submit', False)
    next_status = Result.ResultStatus.SUBMITTED if submit else Result.ResultStatus.DRAFT

    if request.user.role == User.Role.TEACHER and (
        subject.teacher_id is None or subject.teacher.user_id != request.user.id
    ):
        return Response({'detail': 'You may only enter results for your assigned subjects.'}, status=status.HTTP_403_FORBIDDEN)

    created, updated = 0, 0
    with transaction.atomic():
        for row in serializer.validated_data['cleaned_rows']:
            result, is_new = Result.objects.get_or_create(
                student=row['student'],
                subject=subject,
                academic_year=academic_year,
                term=term,
                assessment_type=assessment_type,
                defaults={
                    'marks': row['marks'],
                    'remarks': row['remarks'],
                    'status': next_status,
                    'entered_by': request.user,
                },
            )
            if not is_new:
                if result.status not in (Result.ResultStatus.DRAFT, Result.ResultStatus.RETURNED):
                    continue  # skip already-submitted/approved results
                result.marks = row['marks']
                result.remarks = row['remarks']
                result.status = next_status
                result.save(update_fields=['marks', 'remarks', 'status', 'updated_at'])
                updated += 1
            else:
                created += 1
        AuditLog.objects.create(
            actor=request.user,
            action='CREATE',
            model_name='Result',
            description=f'Bulk entry: {created} created, {updated} updated for {subject.code} {assessment_type} ({term.name}).',
        )
    return Response({'created': created, 'updated': updated}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
@permission_classes([IsResultReader])
def results(request):
    if request.method == 'GET':
        results = Result.objects.select_related(
            'student__user', 'subject', 'term', 'academic_year', 'entered_by', 'approved_by',
        ).prefetch_related('approvals__approved_by').all().order_by('-created_at')
        if request.user.role == User.Role.STUDENT:
            results = results.filter(student__user=request.user, status=Result.ResultStatus.PUBLISHED)
        elif request.user.role == User.Role.TEACHER:
            results = results.filter(
                Q(subject__teacher__user=request.user)
                | Q(subject__school_class__teacher__user=request.user),
            ).distinct()
        student_id = request.query_params.get('student_id')
        if student_id:
            if not student_id.isdecimal():
                return Response({'detail': 'Student ID must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(student_id=int(student_id))
        status_filter = request.query_params.get('status', '').strip().upper()
        if status_filter:
            valid_statuses = {value for value, _ in Result.ResultStatus.choices}
            if status_filter == 'APPROVED_PUBLISHED':
                results = results.filter(status__in=[Result.ResultStatus.APPROVED, Result.ResultStatus.PUBLISHED])
            elif status_filter == 'REVIEW_QUEUE':
                results = results.filter(status__in=[
                    Result.ResultStatus.SUBMITTED,
                    Result.ResultStatus.UNDER_REVIEW,
                ])
            elif status_filter == 'PENDING':
                results = results.filter(status__in=[
                    Result.ResultStatus.DRAFT,
                    Result.ResultStatus.SUBMITTED,
                    Result.ResultStatus.UNDER_REVIEW,
                ])
            elif status_filter in valid_statuses:
                results = results.filter(status=status_filter)
            else:
                return Response({'detail': 'Unknown result status.'}, status=status.HTTP_400_BAD_REQUEST)
        academic_year_id = request.query_params.get('academic_year_id')
        if academic_year_id:
            if not academic_year_id.isdecimal():
                return Response({'detail': 'Academic year ID must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(academic_year_id=int(academic_year_id))
        term_id = request.query_params.get('term_id')
        if term_id:
            if not term_id.isdecimal():
                return Response({'detail': 'Term ID must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(term_id=int(term_id))
        return Response(ResultSerializer(results, many=True, context={'request': request}).data)

    # POST: only Teachers (and Admin/SuperAdmin as emergency override) may enter marks
    if request.user.role not in (*ADMIN_ROLES, User.Role.TEACHER):
        return Response({'detail': 'Only teachers may enter results.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = ResultWriteSerializer(data=request.data)
    if serializer.is_valid():
        requested_status = serializer.validated_data.get('status', Result.ResultStatus.DRAFT)
        if request.user.role != User.Role.TEACHER and requested_status != Result.ResultStatus.DRAFT:
            return Response(
                {'detail': 'New results must start as drafts and follow the review workflow.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.user.role == User.Role.TEACHER and (
            serializer.validated_data['subject'].teacher_id is None
            or serializer.validated_data['subject'].teacher.user_id != request.user.id
            or requested_status not in (Result.ResultStatus.DRAFT, Result.ResultStatus.SUBMITTED)
        ):
            return Response({'detail': 'You may only enter draft or submitted results for your assigned subjects.'}, status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            result = serializer.save(entered_by=request.user)
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='Result',
                description=f'Created result {result.pk} for {result.student.admission_number} in {result.subject.code}.',
            )
        return Response(ResultSerializer(result, context={'request': request}).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAnySystemRole])
def student_academic_report(request, student_id):
    """Build a term report from published results for an enrolled student."""
    role = request.user.role
    if role == User.Role.STUDENT:
        student = Student.objects.select_related('user').filter(user=request.user, pk=student_id).first()
        if student is None:
            return Response({'detail': 'Student report not found.'}, status=status.HTTP_404_NOT_FOUND)
    else:
        student = get_object_or_404(Student.objects.select_related('user'), pk=student_id)
    if role not in (
        User.Role.STUDENT, User.Role.TEACHER, User.Role.SUPER_ADMIN,
        User.Role.ADMIN, User.Role.ACADEMIC_OFFICER,
    ):
        return Response({'detail': 'You do not have permission to view this report.'}, status=status.HTTP_403_FORBIDDEN)

    year_id = request.query_params.get('academic_year_id', '')
    term_id = request.query_params.get('term_id', '')
    if not year_id.isdecimal() or not term_id.isdecimal():
        return Response({'detail': 'Select an academic year and term to generate the report.'}, status=status.HTTP_400_BAD_REQUEST)
    academic_year = get_object_or_404(AcademicYear, pk=int(year_id))
    term = get_object_or_404(Term, pk=int(term_id))
    if term.academic_year_id != academic_year.id:
        return Response({'detail': 'The selected term does not belong to this academic year.'}, status=status.HTTP_400_BAD_REQUEST)
    enrollments = list(Enrollment.objects.select_related(
        'school_class__teacher__user', 'academic_year', 'term',
    ).filter(student=student, academic_year=academic_year, term=term).order_by('id'))
    if not enrollments:
        return Response({'detail': 'The student is not enrolled for this academic year and term.'}, status=status.HTTP_404_NOT_FOUND)
    published = Result.objects.filter(
        student=student,
        subject__school_class__in=[enrollment.school_class for enrollment in enrollments],
        academic_year=academic_year,
        term=term,
        status=Result.ResultStatus.PUBLISHED,
    ).select_related('subject', 'approved_by').order_by('subject__name', 'assessment_type', 'id')
    classes_with_results = set(published.values_list('subject__school_class_id', flat=True))
    enrollment = next(
        (row for row in enrollments if row.school_class_id in classes_with_results),
        enrollments[0],
    )
    if role == User.Role.TEACHER and not (
        enrollment.school_class.teacher_id
        and enrollment.school_class.teacher.user_id == request.user.id
    ) and not enrollment.school_class.subjects.filter(teacher__user=request.user).exists():
        return Response({'detail': 'You may only view reports for your assigned classes.'}, status=status.HTTP_403_FORBIDDEN)

    published = published.filter(subject__school_class=enrollment.school_class)
    grouped = {}
    for result in published:
        row = grouped.setdefault(result.subject_id, {
            'subject': result.subject.name,
            'marks': [],
            'remarks': [],
        })
        row['marks'].append(float(result.marks))
        if result.remarks.strip() and result.remarks.strip() not in row['remarks']:
            row['remarks'].append(result.remarks.strip())

    subjects = []
    for row in grouped.values():
        mark = round(sum(row['marks']) / len(row['marks']), 2)
        subjects.append({
            'subject': row['subject'],
            'marks': mark,
            'grade': Result.calculate_grade(mark),
            'remarks': '; '.join(row['remarks']) or 'No remarks',
        })

    class_enrollments = Enrollment.objects.filter(
        school_class=enrollment.school_class,
        academic_year=enrollment.academic_year,
        term=enrollment.term,
    ).select_related('student__user')
    class_size = class_enrollments.count()
    cohort_subject_results = Result.objects.filter(
        student__enrollments__in=class_enrollments,
        subject__school_class=enrollment.school_class,
        academic_year=enrollment.academic_year,
        term=enrollment.term,
        status=Result.ResultStatus.PUBLISHED,
    ).values('student_id', 'subject_id').annotate(average=Avg('marks'))
    student_average = sum(row['marks'] for row in subjects) / len(subjects) if subjects else None
    position = None
    if student_average is not None:
        cohort_averages = {}
        for row in cohort_subject_results:
            cohort_averages.setdefault(row['student_id'], []).append(float(row['average']))
        position = 1 + sum(
            sum(marks) / len(marks) > student_average
            for marks in cohort_averages.values()
            if marks
        )

    teacher = enrollment.school_class.teacher

    # Approval and publication details
    approvals = list(
        published.exclude(approved_by__isnull=True)
        .order_by('-updated_at')
        .values('approved_by__first_name', 'approved_by__last_name', 'approved_by__username',
                'approved_by__role', 'status', 'updated_at')
    )
    approved_entry = next((a for a in approvals if a['status'] == Result.ResultStatus.APPROVED), None)
    published_entry = next((a for a in approvals if a['status'] == Result.ResultStatus.PUBLISHED), None)

    def _name(entry):
        if not entry:
            return ''
        full = f"{entry.get('approved_by__first_name', '')} {entry.get('approved_by__last_name', '')}".strip()
        return full or entry.get('approved_by__username', '')

    overall_grade = Result.calculate_grade(student_average) if student_average is not None else None
    grade_status_map = {'A': 'Excellent', 'B': 'Very Good', 'C': 'Good', 'D': 'Pass', 'F': 'Fail'}

    return Response({
        'school_name': getattr(settings, 'SCHOOL_NAME', ''),
        'student': {
            'name': student.user.get_full_name() or student.user.username,
            'admission_number': student.admission_number,
            'class_name': str(enrollment.school_class),
        },
        'academic_year': enrollment.academic_year.name,
        'term': enrollment.term.name,
        'subjects': subjects,
        'average': round(student_average, 2) if student_average is not None else None,
        'overall_grade': overall_grade,
        'overall_status': grade_status_map.get(overall_grade, '') if overall_grade else '',
        'position': position,
        'class_size': class_size,
        'class_teacher': (teacher.user.get_full_name() or teacher.user.username) if teacher else '',
        'academic_officer': _name(approved_entry),
        'approved_by': _name(approved_entry),
        'approved_at': approved_entry['updated_at'].isoformat() if approved_entry else None,
        'published_by': _name(published_entry),
        'published_at': published_entry['updated_at'].isoformat() if published_entry else None,
    })


@api_view(['PATCH'])
@permission_classes([IsResultEditor])
def update_result(request, result_id):
    if not isinstance(request.data, Mapping):
        return Response({'detail': 'A JSON object is required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = Result.objects.select_related('subject__teacher').get(pk=result_id)
    except Result.DoesNotExist:
        return Response({'detail': 'Result not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.user.role == User.Role.TEACHER and (
        result.subject.teacher_id is None
        or result.subject.teacher.user_id != request.user.id
        or result.status not in (Result.ResultStatus.DRAFT, Result.ResultStatus.RETURNED)
    ):
        return Response({'detail': 'You may only edit draft or returned results for your assigned subjects.'}, status=status.HTTP_403_FORBIDDEN)

    review_status = request.data.get('status')
    is_reviewer = review_status in (
            Result.ResultStatus.UNDER_REVIEW,
            Result.ResultStatus.APPROVED,
            Result.ResultStatus.RETURNED,
            Result.ResultStatus.PUBLISHED,
    )
    if is_reviewer:
        if request.user.role not in (*ADMIN_ROLES, User.Role.ACADEMIC_OFFICER):
            return Response({'detail': 'Teachers cannot review or publish results.'}, status=status.HTTP_403_FORBIDDEN)
        if review_status == Result.ResultStatus.PUBLISHED and request.user.role == User.Role.ACADEMIC_OFFICER:
            return Response({'detail': 'Academic officers may approve results but cannot publish them. Publishing is reserved for administrators.'}, status=status.HTTP_403_FORBIDDEN)
        if result.entered_by_id == request.user.id:
            return Response({'detail': 'You cannot review a result that you entered.'}, status=status.HTTP_403_FORBIDDEN)
        review_serializer = ResultReviewSerializer(data=request.data)
        if not review_serializer.is_valid():
            return Response(review_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        next_status = review_serializer.validated_data['status']
        allowed_transitions = {
            Result.ResultStatus.SUBMITTED: {Result.ResultStatus.UNDER_REVIEW},
            Result.ResultStatus.UNDER_REVIEW: {Result.ResultStatus.APPROVED, Result.ResultStatus.RETURNED},
            Result.ResultStatus.APPROVED: {Result.ResultStatus.PUBLISHED},
        }
        with transaction.atomic():
            try:
                result = Result.objects.select_for_update(of=('self',)).select_related('subject__teacher').get(pk=result_id)
            except Result.DoesNotExist:
                return Response({'detail': 'Result not found.'}, status=status.HTTP_404_NOT_FOUND)
            if result.entered_by_id == request.user.id:
                return Response({'detail': 'You cannot review a result that you entered.'}, status=status.HTTP_403_FORBIDDEN)
            if next_status not in allowed_transitions.get(result.status, set()):
                return Response({'detail': f'Cannot change a {result.status.lower()} result to {next_status.lower()}.'}, status=status.HTTP_400_BAD_REQUEST)
            # Double-check publish permission inside the lock
            if next_status == Result.ResultStatus.PUBLISHED and request.user.role == User.Role.ACADEMIC_OFFICER:
                return Response({'detail': 'Academic officers may not publish results.'}, status=status.HTTP_403_FORBIDDEN)
            result.status = next_status
            update_fields = ['status', 'updated_at']
            if next_status in (Result.ResultStatus.APPROVED, Result.ResultStatus.RETURNED):
                result.approved_by = request.user
                update_fields.append('approved_by')
            result.save(update_fields=update_fields)
            ResultApproval.objects.create(
                result=result,
                approved_by=request.user,
                decision=result.status,
                comments=review_serializer.validated_data.get('comments', ''),
            )
            AuditLog.objects.create(
                actor=request.user,
                action=result.status,
                model_name='Result',
                description=f'{result.status.title()} result {result.pk}.' + (
                    f' Comment: {review_serializer.validated_data["comments"].strip()}'
                    if review_serializer.validated_data.get('comments', '').strip() else ''
                ),
            )
        return Response(ResultSerializer(result, context={'request': request}).data)

    if 'status' in request.data:
        teacher_submission = (
            request.user.role == User.Role.TEACHER
            and result.status == Result.ResultStatus.DRAFT
            and request.data.get('status') == Result.ResultStatus.SUBMITTED
        )
        if not teacher_submission:
            return Response(
                {'detail': 'Result status changes must follow the review workflow.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if result.status in (Result.ResultStatus.APPROVED, Result.ResultStatus.PUBLISHED):
        return Response(
            {'detail': 'Approved or published results cannot be edited. Use the review workflow for status changes.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.user.role == User.Role.ACADEMIC_OFFICER:
        return Response({'detail': 'Academic officers review and approve results but do not edit marks directly.'}, status=status.HTTP_403_FORBIDDEN)
    if request.user.role == User.Role.TEACHER and set(request.data) - {'marks', 'remarks', 'status'}:
        return Response({'detail': 'Teachers may edit marks, remarks, and submit their assigned draft.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ResultWriteSerializer(result, data=request.data, partial=True)
    if serializer.is_valid():
        auto_draft_returned = request.user.role == User.Role.TEACHER and result.status == Result.ResultStatus.RETURNED and 'status' not in request.data
        if request.user.role == User.Role.TEACHER and (
            serializer.validated_data.get('subject', result.subject).teacher_id is None
            or serializer.validated_data.get('subject', result.subject).teacher.user_id != request.user.id
            or result.status not in (Result.ResultStatus.DRAFT, Result.ResultStatus.RETURNED)
            or serializer.validated_data.get('status', result.status)
            not in (Result.ResultStatus.DRAFT, Result.ResultStatus.SUBMITTED)
        ):
            return Response({'detail': 'You may only submit results for your assigned subjects.'}, status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            updated = serializer.save(**({'status': Result.ResultStatus.DRAFT} if auto_draft_returned else {}))
            AuditLog.objects.create(
                actor=request.user,
                action='UPDATE',
                model_name='Result',
                description=f'Updated result {updated.pk} for {updated.student.admission_number}.',
            )
        return Response(ResultSerializer(updated, context={'request': request}).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAdminOrAcademicOfficer])
def bulk_approve_results(request):
    """Approve, return, or publish multiple results in one request."""
    serializer = BulkApprovalSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    action = serializer.validated_data['action']
    comments = serializer.validated_data.get('comments', '')
    result_ids = serializer.validated_data['result_ids']

    if action == 'publish' and request.user.role not in ADMIN_ROLES:
        return Response({'detail': 'Only administrators may publish results.'}, status=status.HTTP_403_FORBIDDEN)

    transition_map = {
        'approve': (
            {Result.ResultStatus.UNDER_REVIEW},
            Result.ResultStatus.APPROVED,
        ),
        'return': (
            {Result.ResultStatus.UNDER_REVIEW},
            Result.ResultStatus.RETURNED,
        ),
        'publish': (
            {Result.ResultStatus.APPROVED},
            Result.ResultStatus.PUBLISHED,
        ),
    }
    allowed_from, next_status = transition_map[action]

    processed, skipped = 0, 0
    with transaction.atomic():
        results = Result.objects.select_for_update(of=('self',)).filter(pk__in=result_ids)
        for result in results:
            if result.status not in allowed_from or result.entered_by_id == request.user.id:
                skipped += 1
                continue
            result.status = next_status
            update_fields = ['status', 'updated_at']
            if next_status in (Result.ResultStatus.APPROVED, Result.ResultStatus.RETURNED):
                result.approved_by = request.user
                update_fields.append('approved_by')
            result.save(update_fields=update_fields)
            ResultApproval.objects.create(
                result=result, approved_by=request.user,
                decision=next_status, comments=comments,
            )
            processed += 1
        if processed:
            AuditLog.objects.create(
                actor=request.user, action=next_status, model_name='Result',
                description=f'Bulk {action}: {processed} results {next_status.lower()}.{" Comment: " + comments.strip() if comments.strip() else ""}',
            )
    return Response({'processed': processed, 'skipped': skipped})


@api_view(['POST'])
@permission_classes([IsAdminOrAcademicOfficer])
def bulk_enroll_students(request):
    """Enroll multiple students into the same class/term in one request."""
    serializer = BulkEnrollmentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    school_class = serializer.validated_data['school_class']
    academic_year = serializer.validated_data['academic_year']
    term = serializer.validated_data['term']
    students = serializer.validated_data['students']

    created, skipped = 0, 0
    with transaction.atomic():
        for student in students:
            _, is_new = Enrollment.objects.get_or_create(
                student=student, school_class=school_class,
                academic_year=academic_year, term=term,
            )
            if is_new:
                created += 1
            else:
                skipped += 1
        if created:
            AuditLog.objects.create(
                actor=request.user, action='CREATE', model_name='Enrollment',
                description=f'Bulk enrollment: {created} students enrolled in {school_class} for {term.name} ({academic_year.name}).',
            )
    return Response({'created': created, 'skipped': skipped}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdmin])
def bulk_import_users(request):
    """Create multiple student or teacher accounts from a parsed CSV payload."""
    serializer = BulkUserImportSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    role = serializer.validated_data['role']
    rows = serializer.validated_data['cleaned_rows']
    created = 0
    with transaction.atomic():
        for row in rows:
            user = User.objects.create_user(
                username=row['username'], password=row['password'],
                first_name=row['first_name'], last_name=row['last_name'],
                email=row['email'], role=role,
            )
            if role == 'STUDENT':
                Student.objects.create(
                    user=user, admission_number=row['admission_number'],
                    gender=row.get('gender', ''), parent_name=row.get('parent_name', ''),
                )
            else:
                Teacher.objects.create(
                    user=user, employee_id=row['employee_id'],
                    department=row.get('department', ''), qualification=row.get('qualification', ''),
                )
            created += 1
        AuditLog.objects.create(
            actor=request.user, action='CREATE', model_name='User',
            description=f'Bulk import: {created} {role.lower()} accounts created.',
        )
    return Response({'created': created}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAcademicManagerOrTeacher])
def my_classes(request):
    if request.user.role in (*ADMIN_ROLES, User.Role.ACADEMIC_OFFICER):
        classes = SchoolClass.objects.all()
    else:
        classes = SchoolClass.objects.filter(Q(teacher__user=request.user) | Q(subjects__teacher__user=request.user)).distinct()
    classes = classes.select_related('academic_year', 'teacher__user').order_by('name')
    return Response(SchoolClassSerializer(classes, many=True).data)


@api_view(['GET'])
@permission_classes([IsAnySystemRole])
def my_profile(request):
    if request.user.role == User.Role.STUDENT:
        try:
            student = Student.objects.select_related('user').get(user=request.user)
        except Student.DoesNotExist:
            return Response({'detail': 'Student profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudentSerializer(student).data)
    if request.user.role == User.Role.TEACHER:
        try:
            teacher = Teacher.objects.select_related('user').get(user=request.user)
        except Teacher.DoesNotExist:
            return Response({'detail': 'Teacher profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        profile = TeacherSerializer(teacher).data
        profile['account'] = {
            'username': request.user.username,
            'email': request.user.email,
            'role': request.user.role,
            'is_active': request.user.is_active,
            'date_joined': request.user.date_joined,
            'last_login': request.user.last_login,
        }
        return Response(profile)
    return Response({
        'id': request.user.pk,
        'username': request.user.username,
        'name': request.user.get_full_name() or request.user.username,
        'email': request.user.email,
        'role': request.user.role,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAdmin])
def user_list(request):
    if request.method == 'POST':
        serializer = UserManagementSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            with transaction.atomic():
                user = serializer.save()
                AuditLog.objects.create(
                    actor=request.user,
                    action='CREATE',
                    model_name='User',
                    description=f'Created {user.role.lower().replace("_", " ")} account {user.username} ({user.pk}).',
                )
            return Response(UserManagementSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    users = User.objects.all()
    if request.user.role == User.Role.ADMIN:
        users = users.exclude(role__in=ADMIN_ROLES)
    users = users.order_by('username')
    return Response(UserManagementSerializer(users, many=True).data)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAdmin])
def manage_user(request, user_id):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'DELETE':
        if request.user.role != User.Role.SUPER_ADMIN:
            return Response({'detail': 'Only a Super Admin may disable user accounts.'}, status=status.HTTP_403_FORBIDDEN)
        if user.pk == request.user.pk:
            return Response({'detail': 'You cannot disable your own account.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.role == User.Role.SUPER_ADMIN and user.is_active and User.objects.filter(
            role=User.Role.SUPER_ADMIN, is_active=True
        ).count() <= 1:
            return Response({'detail': 'The last active Super Admin cannot be disabled.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user.is_active = False
            user.save(update_fields=['is_active'])
            AuditLog.objects.create(
                actor=request.user,
                action='DISABLE',
                model_name='User',
                description=f'Disabled user account {user.username} ({user.pk}).',
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = UserManagementSerializer(user, data=request.data, partial=True, context={'request': request})
    if serializer.is_valid():
        with transaction.atomic():
            serializer.save()
            changed_fields = ', '.join(sorted(set(request.data.keys()) - {'password'})) or 'account details'
            AuditLog.objects.create(
                actor=request.user,
                action='UPDATE',
                model_name='User',
                description=f'Updated {user.username} ({user.pk}); fields: {changed_fields}.',
            )
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAnySystemRole])
def performance_summary(request):
    approved_results = Q(results__status__in=[Result.ResultStatus.APPROVED, Result.ResultStatus.PUBLISHED])
    subjects = Subject.objects.all()
    if request.user.role == User.Role.TEACHER:
        subjects = subjects.filter(
            Q(teacher__user=request.user) | Q(school_class__teacher__user=request.user),
        ).distinct()
        approved_results &= (
            Q(results__subject__teacher__user=request.user)
            | Q(results__subject__school_class__teacher__user=request.user)
        )
    elif request.user.role == User.Role.STUDENT:
        subjects = subjects.filter(school_class__enrollments__student__user=request.user).distinct()
        approved_results &= Q(results__student__user=request.user, results__status=Result.ResultStatus.PUBLISHED)
    subject_summary = subjects.annotate(
        average_marks=Avg('results__marks', filter=approved_results),
        total_students=Count('results__student', filter=approved_results, distinct=True),
    ).order_by('-average_marks')
    payload = [
        {
            'code': subject.code,
            'name': subject.name,
            'average_marks': round(float(subject.average_marks or 0), 2),
            'total_students': subject.total_students,
        }
        for subject in subject_summary[:8]
    ]
    return Response({'subjects': payload})


@api_view(['GET'])
@permission_classes([IsAdminOrAcademicOfficer])
def audit_logs(request):
    logs = AuditLog.objects.select_related('actor').order_by('-created_at')
    action = request.query_params.get('action', '').strip()
    model_name = request.query_params.get('model', '').strip()
    if action:
        logs = logs.filter(action__iexact=action)
    if model_name:
        logs = logs.filter(model_name__iexact=model_name)
    try:
        limit = int(request.query_params.get('limit', 100))
    except (TypeError, ValueError):
        return Response({'detail': 'Limit must be a number between 1 and 200.'}, status=status.HTTP_400_BAD_REQUEST)
    if not 1 <= limit <= 200:
        return Response({'detail': 'Limit must be a number between 1 and 200.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(AuditLogSerializer(logs[:limit], many=True).data)
