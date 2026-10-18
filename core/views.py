from collections.abc import Mapping

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

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
from .grading import assessment_average
from .student_accounts import create_student_user, issue_student_credentials

ADMIN_ROLES = (User.Role.SUPER_ADMIN, User.Role.ADMIN)
from .serializers import (
    AcademicYearSerializer,
    AuditLogSerializer,
    AssessmentWeightSerializer,
    BulkApprovalSerializer,
    BulkEnrollmentSerializer,
    BulkResultWriteSerializer,
    BulkUserImportSerializer,
    StudentRegistrationImportSerializer,
    generate_admission_number,
    EnrollmentWriteSerializer,
    EnrollmentSerializer,
    ResultSerializer,
    ResultCorrectionRequestSerializer,
    ResultCorrectionReviewSerializer,
    ResultCorrectionSerializer,
    ResultReviewSerializer,
    PromotionPreviewSerializer,
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
    elif role == User.Role.STUDENT:
        students = students.filter(user=request.user)
        teachers = Teacher.objects.none()
        classes = SchoolClass.objects.none()
        subjects = Subject.objects.none()
        result_set = result_set.filter(student__user=request.user, status=Result.ResultStatus.PUBLISHED)

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
    published_rows = list(published_results.values('student_id', 'subject_id', 'assessment_type', 'marks'))
    weight_map = {}
    if active_year and active_term:
        for item in AssessmentWeight.objects.filter(
            subject_id__in={row['subject_id'] for row in published_rows},
            academic_year=active_year, term=active_term,
        ).values('subject_id', 'assessment_type', 'weight'):
            weight_map.setdefault(item['subject_id'], {})[item['assessment_type']] = float(item['weight'])
    student_subject_assessments = {}
    for row in published_rows:
        key = (row['student_id'], row['subject_id'])
        student_subject_assessments.setdefault(key, {}).setdefault(row['assessment_type'], []).append(float(row['marks']))
    student_subject_marks = {}
    for key, assessments in student_subject_assessments.items():
        student_subject_marks[key] = assessment_average(assessments, weight_map.get(key[1], {}))[0]
    average_performance = (
        sum(student_subject_marks.values()) / len(student_subject_marks)
        if student_subject_marks else None
    )
    student_averages = {}
    for (student_id, _subject_id), mark in student_subject_marks.items():
        student_averages.setdefault(student_id, []).append(mark)
    visible_student_ids = set(students.values_list('id', flat=True))
    top_student_ids = sorted(
        ((student_id, sum(marks) / len(marks)) for student_id, marks in student_averages.items()
         if student_id in visible_student_ids and marks),
        key=lambda row: row[1], reverse=True,
    )[:5]
    top_students = {
        student.pk: student for student in Student.objects.filter(pk__in=[row[0] for row in top_student_ids]).select_related('user')
    }
    recent_results = result_set.select_related(
        'student__user', 'subject', 'term', 'academic_year', 'entered_by', 'approved_by'
    ).prefetch_related('approvals__approved_by').order_by('-updated_at')[:6]
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
                'name': top_students[student_id].user.get_full_name() or top_students[student_id].user.username,
                'average': round(float(average), 2),
                'admission_number': top_students[student_id].admission_number,
            }
            for student_id, average in top_student_ids if student_id in top_students
        ],
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAnySystemRole])
def assessment_weights(request):
    if request.method == 'GET':
        rows = AssessmentWeight.objects.select_related('subject', 'academic_year', 'term')
        if request.user.role == User.Role.TEACHER:
            rows = rows.filter(Q(subject__teacher__user=request.user) | Q(subject__school_class__teacher__user=request.user))
        elif request.user.role == User.Role.STUDENT:
            rows = rows.none()
        return Response(AssessmentWeightSerializer(rows.order_by('subject__name', 'assessment_type'), many=True).data)
    if request.user.role not in ADMIN_ROLES:
        return Response({'detail': 'Only administrators may configure assessment weights.'}, status=status.HTTP_403_FORBIDDEN)
    existing = None
    try:
        subject_id = int(request.data.get('subject_id'))
        year_id = int(request.data.get('academic_year_id'))
        term_id = int(request.data.get('term_id'))
        assessment_type = str(request.data.get('assessment_type', '')).strip()
        existing = AssessmentWeight.objects.filter(
            subject_id=subject_id, academic_year_id=year_id, term_id=term_id,
            assessment_type__iexact=assessment_type,
        ).first()
    except (TypeError, ValueError):
        pass
    serializer = AssessmentWeightSerializer(existing, data=request.data)
    if serializer.is_valid():
        weight = serializer.save()
        AuditLog.objects.create(actor=request.user, action='UPDATE' if existing else 'CREATE', model_name='AssessmentWeight', description=f'Set {weight.assessment_type} to {weight.weight}% for {weight.subject.code}, {weight.term}.')
        return Response(AssessmentWeightSerializer(weight).data, status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAnySystemRole])
def academic_years(request):
    if request.method == 'GET':
        years = AcademicYear.objects.all().order_by('-start_date')
        if request.user.role == User.Role.STUDENT:
            years = years.filter(
                Q(enrollments__student__user=request.user)
                | Q(results__student__user=request.user, results__status=Result.ResultStatus.PUBLISHED)
            ).distinct()
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
        if request.user.role == User.Role.STUDENT:
            terms_queryset = terms_queryset.filter(
                Q(enrollments__student__user=request.user)
                | Q(results__student__user=request.user, results__status=Result.ResultStatus.PUBLISHED)
            ).distinct()
        year_id = request.query_params.get('academic_year_id')
        if year_id:
            if not year_id.isdecimal():
                return Response({'detail': 'Academic year ID must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)
            terms_queryset = terms_queryset.filter(academic_year_id=int(year_id))
        return Response(TermSerializer(terms_queryset, many=True).data)
    if request.user.role not in ADMIN_ROLES:
        return Response({'detail': 'Only administrators may add terms.'}, status=status.HTTP_403_FORBIDDEN)
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
        students = Student.objects.select_related('user', 'user__student_activation').all().order_by('admission_number')
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
        payload = StudentSerializer(student).data
        payload['initial_credentials'] = getattr(student, 'initial_credentials', None)
        return Response(payload, status=status.HTTP_201_CREATED)
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


@api_view(['POST'])
@permission_classes([IsAdmin])
def reset_student_login(request, student_id):
    student = get_object_or_404(Student.objects.select_related('user'), pk=student_id)
    credentials = issue_student_credentials(student.user)
    AuditLog.objects.create(
        actor=request.user,
        action='UPDATE',
        model_name='Student',
        description=f'Reissued first-login credentials for student {student.admission_number} ({student.pk}).',
    )
    return Response({'admission_number': student.admission_number, 'full_name': student.user.get_full_name(), **credentials})


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

    if request.user.role not in ADMIN_ROLES:
        return Response({'detail': 'Only administrators may add classes.'}, status=status.HTTP_403_FORBIDDEN)

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
            subjects = subjects.filter(school_class__enrollments__student__user=request.user).filter(
                Q(is_optional=False) | Q(student_registrations__student__user=request.user),
            ).distinct()
        return Response(SubjectSerializer(subjects, many=True).data)

    if request.user.role not in ADMIN_ROLES:
        return Response({'detail': 'Only administrators may add subjects.'}, status=status.HTTP_403_FORBIDDEN)

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


@api_view(['GET', 'POST'])
@permission_classes([IsAnySystemRole])
def subject_registrations(request):
    if request.user.role != User.Role.STUDENT:
        return Response({'detail': 'Subject registration is available to students only.'}, status=status.HTTP_403_FORBIDDEN)
    student = get_object_or_404(Student, user=request.user)
    if request.method == 'GET':
        enrollments = Enrollment.objects.filter(student=student).select_related(
            'school_class', 'academic_year', 'term',
        ).order_by('-academic_year__start_date', 'term__start_date')
        year_id = request.query_params.get('academic_year_id')
        term_id = request.query_params.get('term_id')
        if year_id and year_id.isdecimal():
            enrollments = enrollments.filter(academic_year_id=int(year_id))
        if term_id and term_id.isdecimal():
            enrollments = enrollments.filter(term_id=int(term_id))
        data = []
        for enrollment in enrollments:
            registered_ids = set(StudentSubjectRegistration.objects.filter(
                student=student, academic_year=enrollment.academic_year, term=enrollment.term,
                subject__school_class=enrollment.school_class,
            ).values_list('subject_id', flat=True))
            items = Subject.objects.filter(school_class=enrollment.school_class).select_related(
                'teacher__user', 'school_class__academic_year',
            ).order_by('code')
            subjects_data = SubjectSerializer(items, many=True).data
            for item in subjects_data:
                item['is_registered'] = item['id'] in registered_ids or not item['is_optional']
            data.append({
                'school_class': SchoolClassSerializer(enrollment.school_class).data,
                'academic_year': AcademicYearSerializer(enrollment.academic_year).data,
                'term': {'id': enrollment.term_id, 'name': enrollment.term.name},
                'max_optional_subjects': enrollment.school_class.max_optional_subjects,
                'subjects': subjects_data,
            })
        return Response(data)

    school_class_id = request.data.get('school_class_id')
    term_id = request.data.get('term_id')
    subject_ids = request.data.get('subject_ids')
    if not str(school_class_id or '').isdecimal() or not str(term_id or '').isdecimal() or not isinstance(subject_ids, list):
        return Response({'detail': 'Provide school_class_id, term_id, and a list of subject_ids.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        enrollment = Enrollment.objects.select_related('school_class', 'academic_year', 'term').get(
            student=student, school_class_id=int(school_class_id), term_id=int(term_id),
        )
    except Enrollment.DoesNotExist:
        return Response({'detail': 'You are not enrolled in this class and term.'}, status=status.HTTP_400_BAD_REQUEST)
    if enrollment.term.academic_year_id != enrollment.academic_year_id or enrollment.school_class.academic_year_id != enrollment.academic_year_id:
        return Response({'detail': 'The enrollment has an inconsistent academic year and term.'}, status=status.HTTP_400_BAD_REQUEST)
    if any(not str(item).isdecimal() for item in subject_ids) or len(set(map(str, subject_ids))) != len(subject_ids):
        return Response({'detail': 'Subject IDs must be unique positive integers.'}, status=status.HTTP_400_BAD_REQUEST)
    optional_subjects = Subject.objects.filter(
        school_class=enrollment.school_class, is_optional=True,
    )
    selected_ids = set(map(int, subject_ids))
    if selected_ids - set(optional_subjects.values_list('id', flat=True)):
        return Response({'detail': 'Only optional subjects assigned to your enrolled class may be selected.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(selected_ids) > enrollment.school_class.max_optional_subjects:
        return Response({'detail': f'You may select up to {enrollment.school_class.max_optional_subjects} optional subjects.'}, status=status.HTTP_400_BAD_REQUEST)
    current = set(StudentSubjectRegistration.objects.filter(
        student=student, academic_year=enrollment.academic_year, term=enrollment.term,
        subject__school_class=enrollment.school_class,
    ).values_list('subject_id', flat=True))
    if current - selected_ids and Result.objects.filter(
        student=student, subject_id__in=current - selected_ids,
        academic_year=enrollment.academic_year, term=enrollment.term,
    ).exists():
        return Response({'detail': 'Selections cannot be changed after marks have been recorded for those subjects.'}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        StudentSubjectRegistration.objects.filter(
            student=student, academic_year=enrollment.academic_year, term=enrollment.term,
            subject__school_class=enrollment.school_class,
        ).exclude(subject_id__in=selected_ids).delete()
        for subject_id in selected_ids:
            StudentSubjectRegistration.objects.get_or_create(
                student=student, subject_id=subject_id,
                academic_year=enrollment.academic_year, term=enrollment.term,
            )
    return Response({'detail': 'Optional subject selection saved.', 'selected_subject_ids': sorted(selected_ids)})


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
    submit = serializer.validated_data['submit']
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
                result.save(update_fields=['marks', 'grade', 'remarks', 'status', 'updated_at'])
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

    enrolled_classes = [e.school_class for e in enrollments]

    if role == User.Role.TEACHER:
        accessible = [
            sc for sc in enrolled_classes
            if (sc.teacher_id and sc.teacher.user_id == request.user.id)
            or sc.subjects.filter(teacher__user=request.user).exists()
        ]
        if not accessible:
            return Response({'detail': 'You may only view reports for your assigned classes.'}, status=status.HTTP_403_FORBIDDEN)
        accessible_ids = {school_class.id for school_class in accessible}
        enrollments = [e for e in enrollments if e.school_class_id in accessible_ids]
        enrolled_classes = accessible

    published = Result.objects.filter(
        student=student,
        subject__school_class__in=enrolled_classes,
        academic_year=academic_year,
        term=term,
        status=Result.ResultStatus.PUBLISHED,
    ).select_related('subject', 'approved_by').order_by('subject__name', 'assessment_type', 'id')

    # Use the first enrollment for class-level metadata (teacher, class name)
    enrollment = enrollments[0]

    grouped = {
        subject.pk: {
            'subject': subject.name,
            'marks': [],
            'assessment_marks': {},
            'remarks': [],
        }
        for subject in Subject.objects.filter(school_class__in=enrolled_classes).only('id', 'name')
    }
    for result in published:
        row = grouped[result.subject_id]
        row['marks'].append(float(result.marks))
        row['assessment_marks'].setdefault(result.assessment_type, []).append(float(result.marks))
        if result.remarks.strip() and result.remarks.strip() not in row['remarks']:
            row['remarks'].append(result.remarks.strip())

    subjects = []
    weight_rows = AssessmentWeight.objects.filter(
        subject_id__in=grouped.keys(), academic_year=academic_year, term=term,
    ).values('subject_id', 'assessment_type', 'weight')
    weights_by_subject = {}
    for weight_row in weight_rows:
        weights_by_subject.setdefault(weight_row['subject_id'], {})[weight_row['assessment_type']] = float(weight_row['weight'])
    for subject_id, row in grouped.items():
        type_weights = weights_by_subject.get(subject_id, {})
        assessment_marks = row['assessment_marks']
        mark, weighted = assessment_average(assessment_marks, type_weights)
        mark = round(mark, 2) if mark is not None else None
        assessment_breakdown = [
            {
                'assessment_type': assessment_type,
                'marks': round(sum(assessment_marks[assessment_type]) / len(assessment_marks[assessment_type]), 2) if assessment_type in assessment_marks else None,
                'weight': type_weights.get(assessment_type),
            }
            for assessment_type in dict.fromkeys([*assessment_marks.keys(), *type_weights.keys()])
        ]
        subjects.append({
            'subject_id': subject_id,
            'subject': row['subject'],
            'marks': mark,
            'weighted': weighted,
            'assessment_breakdown': assessment_breakdown,
            'has_missing_assessments': not assessment_marks or any(item['marks'] is None for item in assessment_breakdown),
            'grade': Result.calculate_grade(mark) if mark is not None else None,
            'grade_description': {
                'A': 'Excellent', 'B': 'Very Good', 'C': 'Good',
                'D': 'Pass', 'E': 'Needs Improvement', 'F': 'Fail',
            }.get(Result.calculate_grade(mark)) if mark is not None else None,
            'outcome': ('Pass' if mark >= 50 else 'Fail') if mark is not None else None,
            'remarks': '; '.join(row['remarks']) or 'No subject remark',
        })

    # Build a subject_id -> school_class_id map from published results
    subject_class_map = {r.subject_id: r.subject.school_class_id for r in published}

    # Per-class cohort: students enrolled in each specific class
    class_ids = list({e.school_class_id for e in enrollments})
    # For each class, get the set of student PKs enrolled
    class_student_ids = {}
    for class_id in class_ids:
        class_student_ids[class_id] = set(
            Student.objects.filter(
                enrollments__school_class_id=class_id,
                enrollments__academic_year=academic_year,
                enrollments__term=term,
            ).distinct().values_list('pk', flat=True)
        )

    # class_size for the student's primary class (first enrollment)
    primary_class_id = enrollments[0].school_class_id
    class_size = len(class_student_ids.get(primary_class_id, set()))

    # Per-subject cohort results scoped to the subject's own class
    cohort_subject_results = Result.objects.filter(
        subject__school_class__in=enrolled_classes,
        academic_year=academic_year,
        term=term,
        status=Result.ResultStatus.PUBLISHED,
    ).values('student_id', 'subject_id', 'subject__school_class_id', 'assessment_type').annotate(average=Avg('marks'))
    cohort_rows = list(cohort_subject_results)
    cohort_subject_ids = {row['subject_id'] for row in cohort_rows}
    cohort_weights = {}
    for weight_row in AssessmentWeight.objects.filter(
        subject_id__in=cohort_subject_ids, academic_year=academic_year, term=term,
    ).values('subject_id', 'assessment_type', 'weight'):
        cohort_weights.setdefault(weight_row['subject_id'], {})[weight_row['assessment_type']] = float(weight_row['weight'])

    cohort_assessments = {}
    class_by_subject = {}
    for cohort_row in cohort_rows:
        key = (cohort_row['subject_id'], cohort_row['student_id'])
        cohort_assessments.setdefault(key, {}).setdefault(cohort_row['assessment_type'], []).append(float(cohort_row['average']))
        class_by_subject[cohort_row['subject_id']] = cohort_row['subject__school_class_id']

    # Subject ranks use each student's weighted subject mark where configured.
    cohort_marks_by_subject = {}
    for (subject_id, student_id), assessment_marks in cohort_assessments.items():
        student_mark, _ = assessment_average(assessment_marks, cohort_weights.get(subject_id, {}))
        subj_class_id = class_by_subject[subject_id]
        enrolled_in_class = class_student_ids.get(subj_class_id, set())
        if student_id in enrolled_in_class:
            cohort_marks_by_subject.setdefault(subject_id, []).append(
                (student_id, student_mark)
            )

    for subject in subjects:
        subject_id = subject.pop('subject_id')
        cohort_marks = cohort_marks_by_subject.get(subject_id, [])
        student_mark = next((mark for sid, mark in cohort_marks if sid == student.pk), None)
        subj_class_id = subject_class_map.get(subject_id, primary_class_id)
        subject['position'] = (
            1 + sum(mark > student_mark for _, mark in cohort_marks)
            if student_mark is not None else None
        )
        subject['class_size'] = len(class_student_ids.get(subj_class_id, set()))

    available_marks = [row['marks'] for row in subjects if row['marks'] is not None]
    student_average = sum(available_marks) / len(available_marks) if available_marks else None

    # Overall position: rank within the primary class
    position = None
    if student_average is not None:
        primary_student_ids = class_student_ids.get(primary_class_id, set())
        # Collect per-student averages for peers in the primary class
        cohort_averages = {}
        for (subject_id, student_id), assessment_marks in cohort_assessments.items():
            if student_id in primary_student_ids and class_by_subject[subject_id] == primary_class_id:
                subject_mark, _ = assessment_average(assessment_marks, cohort_weights.get(subject_id, {}))
                cohort_averages.setdefault(student_id, []).append(subject_mark)
        position = 1 + sum(
            sum(marks) / len(marks) > student_average
            for marks in cohort_averages.values()
            if marks
        )

    teacher = enrollment.school_class.teacher
    approval_entries = list(
        ResultApproval.objects.filter(
            result__in=published,
            decision__in=(Result.ResultStatus.APPROVED, Result.ResultStatus.PUBLISHED),
        ).select_related('approved_by').order_by('-created_at')
    )
    approved_entry = next(
        (entry for entry in approval_entries if entry.decision == Result.ResultStatus.APPROVED), None,
    )
    published_entry = next(
        (entry for entry in approval_entries if entry.decision == Result.ResultStatus.PUBLISHED), None,
    )

    def _name(entry):
        if not entry or not entry.approved_by:
            return ''
        return entry.approved_by.get_full_name() or entry.approved_by.username

    overall_grade = Result.calculate_grade(student_average) if student_average is not None else None
    grade_description_map = {
        'A': 'Excellent', 'B': 'Very Good', 'C': 'Good', 'D': 'Pass', 'E': 'Needs Improvement', 'F': 'Fail',
    }
    overall_status = 'Pass' if student_average is not None and student_average >= 50 else 'Fail' if student_average is not None else ''

    unique_class_names = list(dict.fromkeys(str(e.school_class) for e in enrollments))

    return Response({
        'school_name': getattr(settings, 'SCHOOL_NAME', ''),
        'school_logo_url': getattr(settings, 'SCHOOL_LOGO_URL', ''),
        'school_address': getattr(settings, 'SCHOOL_ADDRESS', ''),
        'school_phone': getattr(settings, 'SCHOOL_PHONE', ''),
        'school_email': getattr(settings, 'SCHOOL_EMAIL', ''),
        'student': {
            'name': student.user.get_full_name() or student.user.username,
            'admission_number': student.admission_number,
            'class_name': ', '.join(unique_class_names),
        },
        'academic_year': enrollment.academic_year.name,
        'term': enrollment.term.name,
        'subjects': subjects,
        'average': round(student_average, 2) if student_average is not None else None,
        'overall_grade': overall_grade,
        'overall_grade_description': grade_description_map.get(overall_grade, '') if overall_grade else '',
        'overall_status': overall_status,
        'overall_comment': None,
        'position': position,
        'class_size': class_size,
        'class_teacher': (teacher.user.get_full_name() or teacher.user.username) if teacher else '',
        'academic_officer': _name(approved_entry),
        'approved_by': _name(approved_entry),
        'approved_at': approved_entry.created_at.isoformat() if approved_entry else None,
        'approval_comment': approved_entry.comments if approved_entry else '',
        'published_by': _name(published_entry),
        'published_at': published_entry.created_at.isoformat() if published_entry else None,
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
def preview_student_import(request):
    serializer = StudentRegistrationImportSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data
    return Response({
        'total': len(data['rows']),
        'valid': len(data['valid_rows']),
        'duplicates': data['duplicates'],
        'errors': data['row_errors'],
    })


@api_view(['POST'])
@permission_classes([IsAdmin])
def import_students(request):
    serializer = StudentRegistrationImportSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data
    created = 0
    credentials = []
    with transaction.atomic():
        admission_prefix = f'STU-{timezone.now().year}-'
        first_available = generate_admission_number()
        next_admission_sequence = int(first_available[len(admission_prefix):])
        reserved_admissions = {row['admission_number'] for row in data['valid_rows'] if row['admission_number']}
        active_term = data['import_term']
        for row in data['valid_rows']:
            admission = row['admission_number']
            if not admission:
                admission = f'{admission_prefix}{next_admission_sequence:04d}'
                while admission in reserved_admissions:
                    next_admission_sequence += 1
                    admission = f'{admission_prefix}{next_admission_sequence:04d}'
                reserved_admissions.add(admission)
                next_admission_sequence += 1
            user, login_details = create_student_user(
                first_name=row['first_name'],
                last_name=row['last_name'],
                email=row['email'],
            )
            student = Student.objects.create(
                user=user,
                admission_number=admission,
                middle_name=row['middle_name'],
                date_of_birth=row['date_of_birth'],
                gender=row['gender'],
                parent_name=row['parent_name'],
                parent_phone=row['parent_phone'],
                current_class=row['current_class'],
            )
            if row['school_class'] and active_term:
                Enrollment.objects.get_or_create(
                    student=student,
                    school_class=row['school_class'],
                    academic_year=row['school_class'].academic_year,
                    term=active_term,
                )
            credentials.append({'admission_number': admission, 'full_name': student.user.get_full_name(), **login_details})
            created += 1
        if created:
            AuditLog.objects.create(
                actor=request.user,
                action='CREATE',
                model_name='Student',
                description=f'CSV registration: {created} students created with temporary passwords requiring first-login change.',
            )
    return Response({
        'created': created,
        'skipped': len(data['duplicates']) + len(data['row_errors']),
        'duplicates': data['duplicates'],
        'errors': data['row_errors'],
        'credentials': credentials,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdmin])
def bulk_import_users(request):
    """Create multiple student or teacher accounts from a parsed CSV payload."""
    serializer = BulkUserImportSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    role = serializer.validated_data['role']
    if role == 'STUDENT':
        return Response({'detail': 'Use student registration import; student CSV files must not contain usernames or passwords.'}, status=status.HTTP_400_BAD_REQUEST)
    rows = serializer.validated_data['cleaned_rows']
    created = 0
    with transaction.atomic():
        for row in rows:
            user = User.objects.create_user(
                username=row['username'], password=row.get('password'),
                first_name=row['first_name'], last_name=row['last_name'],
                email=row['email'], role=role,
            )
            if role == 'STUDENT':
                Student.objects.create(
                    user=user, admission_number=row.get('admission_number') or generate_admission_number(),
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
    return Response({
        'created': created,
        'skipped': len(serializer.validated_data['row_errors']),
        'errors': serializer.validated_data['row_errors'],
    }, status=status.HTTP_201_CREATED)


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
    result_rows = Result.objects.filter(status__in=[Result.ResultStatus.APPROVED, Result.ResultStatus.PUBLISHED])
    if request.user.role == User.Role.TEACHER:
        result_rows = result_rows.filter(
            Q(subject__teacher__user=request.user) | Q(subject__school_class__teacher__user=request.user),
        )
    elif request.user.role == User.Role.STUDENT:
        result_rows = result_rows.filter(student__user=request.user, status=Result.ResultStatus.PUBLISHED)
    rows = list(result_rows.values(
        'student_id', 'subject_id', 'subject__code', 'subject__name',
        'academic_year_id', 'term_id', 'assessment_type', 'marks',
    ))
    policy_map = {}
    for policy in AssessmentWeight.objects.filter(
        subject_id__in={row['subject_id'] for row in rows},
        academic_year_id__in={row['academic_year_id'] for row in rows},
        term_id__in={row['term_id'] for row in rows},
    ).values('subject_id', 'academic_year_id', 'term_id', 'assessment_type', 'weight'):
        key = (policy['subject_id'], policy['academic_year_id'], policy['term_id'])
        policy_map.setdefault(key, {})[policy['assessment_type']] = float(policy['weight'])
    grouped_results = {}
    subject_names = {}
    for row in rows:
        key = (row['student_id'], row['subject_id'], row['academic_year_id'], row['term_id'])
        grouped_results.setdefault(key, {}).setdefault(row['assessment_type'], []).append(float(row['marks']))
        subject_names[row['subject_id']] = (row['subject__code'], row['subject__name'])
    subject_marks = {}
    subject_students = {}
    for (student_id, subject_id, year_id, term_id), assessments in grouped_results.items():
        mark, _ = assessment_average(assessments, policy_map.get((subject_id, year_id, term_id), {}))
        subject_marks.setdefault(subject_id, []).append(mark)
        subject_students.setdefault(subject_id, set()).add(student_id)
    payload = []
    for subject_id, marks in subject_marks.items():
        code, name = subject_names[subject_id]
        payload.append({
            'code': code,
            'name': name,
            'average_marks': round(sum(marks) / len(marks), 2),
            'total_students': len(subject_students[subject_id]),
        })
    payload.sort(key=lambda item: item['average_marks'], reverse=True)
    payload = payload[:8]
    return Response({'subjects': payload})


@api_view(['GET'])
@permission_classes([IsAnySystemRole])
def academic_history(request, student_id):
    """Return all enrollments with published result summaries for a student."""
    role = request.user.role
    if role == User.Role.STUDENT:
        student = Student.objects.filter(user=request.user, pk=student_id).first()
        if student is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    elif role == User.Role.TEACHER:
        student = Student.objects.filter(
            pk=student_id,
            enrollments__school_class__in=SchoolClass.objects.filter(
                Q(teacher__user=request.user) | Q(subjects__teacher__user=request.user)
            ),
        ).distinct().first()
        if student is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    else:
        student = get_object_or_404(Student, pk=student_id)

    enrollments_qs = (
        Enrollment.objects
        .filter(student=student)
        .select_related('school_class__teacher__user', 'academic_year', 'term')
        .order_by('academic_year__start_date', 'term__start_date')
    )

    published_results = (
        Result.objects
        .filter(student=student, status=Result.ResultStatus.PUBLISHED)
        .values('academic_year_id', 'term_id', 'subject_id', 'assessment_type', 'marks')
    )
    weight_rows = AssessmentWeight.objects.filter(
        subject_id__in={r['subject_id'] for r in published_results},
        academic_year_id__in={r['academic_year_id'] for r in published_results},
        term_id__in={r['term_id'] for r in published_results},
    ).values('subject_id', 'academic_year_id', 'term_id', 'assessment_type', 'weight')
    weight_map = {}
    for w in weight_rows:
        weight_map.setdefault((w['subject_id'], w['academic_year_id'], w['term_id']), {})[w['assessment_type']] = float(w['weight'])

    # Group assessments per (year, term, subject)
    term_subject_assessments = {}
    for r in published_results:
        key = (r['academic_year_id'], r['term_id'])
        subj_key = (r['subject_id'], r['academic_year_id'], r['term_id'])
        term_subject_assessments.setdefault(key, {}).setdefault(subj_key, {}).setdefault(r['assessment_type'], []).append(float(r['marks']))

    # Compute per-term summary
    term_summaries = {}
    for (year_id, term_id), subjects_data in term_subject_assessments.items():
        subject_marks = []
        for subj_key, assessments in subjects_data.items():
            mark, _ = assessment_average(assessments, weight_map.get(subj_key, {}))
            if mark is not None:
                subject_marks.append(mark)
        avg = round(sum(subject_marks) / len(subject_marks), 2) if subject_marks else None
        term_summaries[(year_id, term_id)] = {
            'average': avg,
            'subjects_count': len(subjects_data),
            'overall_grade': Result.calculate_grade(avg) if avg is not None else None,
            'overall_status': ('Pass' if avg >= 50 else 'Fail') if avg is not None else None,
        }

    # Compute per-term class position
    for (year_id, term_id), summary in term_summaries.items():
        if summary['average'] is None:
            summary['position'] = None
            summary['class_size'] = None
            continue
        # Find the class this student was in for this term
        enrollment_for_term = next(
            (e for e in enrollments_qs if e.academic_year_id == year_id and e.term_id == term_id), None
        )
        if not enrollment_for_term:
            summary['position'] = None
            summary['class_size'] = None
            continue
        class_id = enrollment_for_term.school_class_id
        peer_ids = set(
            Student.objects.filter(
                enrollments__school_class_id=class_id,
                enrollments__academic_year_id=year_id,
                enrollments__term_id=term_id,
            ).distinct().values_list('pk', flat=True)
        )
        summary['class_size'] = len(peer_ids)
        peer_results = (
            Result.objects
            .filter(
                student_id__in=peer_ids,
                subject__school_class_id=class_id,
                academic_year_id=year_id,
                term_id=term_id,
                status=Result.ResultStatus.PUBLISHED,
            )
            .values('student_id', 'subject_id', 'assessment_type', 'marks')
        )
        peer_subject_assessments = {}
        for pr in peer_results:
            subj_key = (pr['subject_id'], year_id, term_id)
            peer_subject_assessments.setdefault(pr['student_id'], {}).setdefault(subj_key, {}).setdefault(pr['assessment_type'], []).append(float(pr['marks']))
        peer_averages = []
        for peer_id, peer_subjects in peer_subject_assessments.items():
            peer_marks = []
            for subj_key, assessments in peer_subjects.items():
                m, _ = assessment_average(assessments, weight_map.get(subj_key, {}))
                if m is not None:
                    peer_marks.append(m)
            if peer_marks:
                peer_averages.append(sum(peer_marks) / len(peer_marks))
        summary['position'] = 1 + sum(p > summary['average'] for p in peer_averages)

    # Build grouped history: year -> terms
    history = {}
    for enrollment in enrollments_qs:
        year_key = enrollment.academic_year_id
        if year_key not in history:
            history[year_key] = {
                'academic_year_id': enrollment.academic_year_id,
                'academic_year': enrollment.academic_year.name,
                'terms': {},
            }
        term_key = enrollment.term_id
        if term_key not in history[year_key]['terms']:
            summary = term_summaries.get((enrollment.academic_year_id, enrollment.term_id), {})
            history[year_key]['terms'][term_key] = {
                'term_id': enrollment.term_id,
                'term': enrollment.term.name,
                'class_name': str(enrollment.school_class),
                'class_id': enrollment.school_class_id,
                **summary,
            }

    result = [
        {
            **year_data,
            'terms': list(year_data['terms'].values()),
        }
        for year_data in history.values()
    ]
    return Response({
        'student': {
            'name': student.user.get_full_name() or student.user.username,
            'admission_number': student.admission_number,
        },
        'history': result,
    })


@api_view(['POST'])
@permission_classes([IsAdmin])
def bulk_promote_students(request):
    """Enroll a list of students into a new class/term (promotion or new year).

    Expects: { student_ids, school_class_id, academic_year_id, term_id }
    Reuses BulkEnrollmentSerializer — same validation, different audit message.
    """
    serializer = BulkEnrollmentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    school_class = serializer.validated_data['school_class']
    academic_year = serializer.validated_data['academic_year']
    term = serializer.validated_data['term']
    students_list = serializer.validated_data['students']

    created, skipped = 0, 0
    with transaction.atomic():
        for student in students_list:
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
                actor=request.user, action='PROMOTE', model_name='Enrollment',
                description=(
                    f'Bulk promotion: {created} students enrolled in {school_class} '
                    f'for {term.name} ({academic_year.name}).'
                ),
            )
    return Response({'created': created, 'skipped': skipped}, status=status.HTTP_201_CREATED)



@api_view(['GET'])
@permission_classes([IsAdminOrAcademicOfficer])
def promotion_preview(request):
    """Preview which students are eligible for promotion based on published results."""
    serializer = PromotionPreviewSerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    source_class_ids = serializer.validated_data['source_class_ids']
    academic_year = serializer.validated_data['academic_year']
    term = serializer.validated_data['term']
    pass_mark = float(serializer.validated_data['pass_mark'])

    if term.academic_year_id != academic_year.id:
        return Response({'detail': 'Term must belong to the selected academic year.'}, status=status.HTTP_400_BAD_REQUEST)

    enrolled_students = Student.objects.filter(
        enrollments__school_class_id__in=source_class_ids,
        enrollments__academic_year=academic_year,
        enrollments__term=term,
    ).distinct().select_related('user')

    published = (
        Result.objects
        .filter(
            student__in=enrolled_students,
            subject__school_class_id__in=source_class_ids,
            academic_year=academic_year,
            term=term,
            status=Result.ResultStatus.PUBLISHED,
        )
        .values('student_id', 'subject_id', 'assessment_type', 'marks')
    )

    weight_rows = AssessmentWeight.objects.filter(
        subject__school_class_id__in=source_class_ids,
        academic_year=academic_year,
        term=term,
    ).values('subject_id', 'assessment_type', 'weight')
    weight_map = {}
    for w in weight_rows:
        weight_map.setdefault(w['subject_id'], {})[w['assessment_type']] = float(w['weight'])

    student_subject_assessments = {}
    for row in published:
        student_subject_assessments.setdefault(row['student_id'], {}).setdefault(
            row['subject_id'], {}
        ).setdefault(row['assessment_type'], []).append(float(row['marks']))

    eligible, not_eligible, no_results = [], [], []
    for student in enrolled_students:
        subjects_data = student_subject_assessments.get(student.pk, {})
        if not subjects_data:
            no_results.append({
                'id': student.pk,
                'name': student.user.get_full_name() or student.user.username,
                'admission_number': student.admission_number,
                'average': None,
            })
            continue
        marks = []
        for subject_id, assessments in subjects_data.items():
            mark, _ = assessment_average(assessments, weight_map.get(subject_id, {}))
            if mark is not None:
                marks.append(mark)
        average = round(sum(marks) / len(marks), 2) if marks else None
        entry = {
            'id': student.pk,
            'name': student.user.get_full_name() or student.user.username,
            'admission_number': student.admission_number,
            'average': average,
        }
        if average is not None and average >= pass_mark:
            eligible.append(entry)
        else:
            not_eligible.append(entry)

    eligible.sort(key=lambda x: x['average'] or 0, reverse=True)
    not_eligible.sort(key=lambda x: x['average'] or 0, reverse=True)

    return Response({
        'pass_mark': pass_mark,
        'eligible': eligible,
        'not_eligible': not_eligible,
        'no_results': no_results,
        'summary': {
            'eligible': len(eligible),
            'not_eligible': len(not_eligible),
            'no_results': len(no_results),
            'total': len(eligible) + len(not_eligible) + len(no_results),
        },
    })


@api_view(['POST'])
@permission_classes([IsResultEditor])
def request_result_correction(request, result_id):
    """Teacher or admin requests a correction to a published result."""
    try:
        result = Result.objects.select_related('subject__teacher', 'student').get(pk=result_id)
    except Result.DoesNotExist:
        return Response({'detail': 'Result not found.'}, status=status.HTTP_404_NOT_FOUND)

    if result.status != Result.ResultStatus.PUBLISHED:
        return Response({'detail': 'Only published results can be corrected.'}, status=status.HTTP_400_BAD_REQUEST)

    if request.user.role == User.Role.TEACHER and (
        result.subject.teacher_id is None or result.subject.teacher.user_id != request.user.id
    ):
        return Response({'detail': 'You may only request corrections for your assigned subjects.'}, status=status.HTTP_403_FORBIDDEN)

    if ResultCorrection.objects.filter(result=result, status=ResultCorrection.CorrectionStatus.PENDING).exists():
        return Response({'detail': 'A correction request is already pending for this result.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ResultCorrectionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        correction = ResultCorrection.objects.create(
            result=result,
            requested_by=request.user,
            old_marks=result.marks,
            new_marks=serializer.validated_data['new_marks'],
            reason=serializer.validated_data['reason'],
        )
        AuditLog.objects.create(
            actor=request.user,
            action='CORRECTION_REQUESTED',
            model_name='Result',
            description=(
                f'Correction requested for result {result.pk} '
                f'({result.student.admission_number} - {result.subject.code}): '
                f'{result.marks} -> {correction.new_marks}. Reason: {correction.reason}'
            ),
        )
    return Response(ResultCorrectionSerializer(correction).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAdminOrAcademicOfficer])
def list_result_corrections(request):
    """List pending (or all) correction requests."""
    corrections = ResultCorrection.objects.select_related(
        'result__student__user', 'result__subject', 'requested_by', 'reviewed_by',
    ).order_by('-created_at')
    status_filter = request.query_params.get('status', '').strip().upper()
    if status_filter in (s for s, _ in ResultCorrection.CorrectionStatus.choices):
        corrections = corrections.filter(status=status_filter)
    return Response(ResultCorrectionSerializer(corrections, many=True).data)


@api_view(['POST'])
@permission_classes([IsAdminOrAcademicOfficer])
def review_result_correction(request, correction_id):
    """Academic officer approves or rejects a correction request."""
    try:
        correction = ResultCorrection.objects.select_related('result__subject__teacher').get(pk=correction_id)
    except ResultCorrection.DoesNotExist:
        return Response({'detail': 'Correction request not found.'}, status=status.HTTP_404_NOT_FOUND)

    if correction.status != ResultCorrection.CorrectionStatus.PENDING:
        return Response({'detail': 'This correction has already been reviewed.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ResultCorrectionReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    action = serializer.validated_data['action']
    with transaction.atomic():
        correction_locked = ResultCorrection.objects.select_for_update().get(pk=correction_id)
        if correction_locked.status != ResultCorrection.CorrectionStatus.PENDING:
            return Response({'detail': 'This correction has already been reviewed.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.utils import timezone as tz
        correction_locked.reviewed_by = request.user
        correction_locked.review_comment = serializer.validated_data.get('review_comment', '')
        correction_locked.reviewed_at = tz.now()

        if action == 'approve':
            correction_locked.status = ResultCorrection.CorrectionStatus.APPROVED
            result = correction_locked.result
            result.marks = correction_locked.new_marks
            result.save(update_fields=['marks', 'grade', 'updated_at'])
            AuditLog.objects.create(
                actor=request.user,
                action='CORRECTION_APPROVED',
                model_name='Result',
                description=(
                    f'Correction approved for result {result.pk} '
                    f'({result.student.admission_number} - {result.subject.code}): '
                    f'{correction_locked.old_marks} -> {correction_locked.new_marks}.'
                ),
            )
        else:
            correction_locked.status = ResultCorrection.CorrectionStatus.REJECTED
            AuditLog.objects.create(
                actor=request.user,
                action='CORRECTION_REJECTED',
                model_name='Result',
                description=(
                    f'Correction rejected for result {correction_locked.result.pk}. '
                    f'Comment: {correction_locked.review_comment}'
                ),
            )
        correction_locked.save(update_fields=['status', 'reviewed_by', 'review_comment', 'reviewed_at'])

    return Response(ResultCorrectionSerializer(correction_locked).data)


@api_view(['GET'])
@permission_classes([IsAdmin])
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
