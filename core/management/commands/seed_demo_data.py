from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import (
    AcademicYear,
    Enrollment,
    Result,
    SchoolClass,
    Student,
    Subject,
    Teacher,
    Term,
    User,
)


class Command(BaseCommand):
    help = 'Seed demo data for the student results system.'

    def handle(self, *args, **options):
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@school.local', 'role': User.Role.SUPER_ADMIN, 'is_staff': True, 'is_superuser': True},
        )
        if not admin_user.has_usable_password():
            admin_user.set_password('admin123')
            admin_user.save()

        academic_officer, _ = User.objects.get_or_create(
            username='academic_officer',
            defaults={'email': 'officer@school.local', 'role': User.Role.ACADEMIC_OFFICER},
        )
        if not academic_officer.has_usable_password():
            academic_officer.set_password('officer123')
            academic_officer.save()

        year, _ = AcademicYear.objects.get_or_create(
            name='2025/2026',
            defaults={'start_date': '2025-01-01', 'end_date': '2026-12-31', 'is_active': True},
        )

        term, _ = Term.objects.get_or_create(
            academic_year=year,
            name='Term 1',
            defaults={'start_date': '2025-01-01', 'end_date': '2025-03-31', 'is_active': True},
        )

        teacher_user, _ = User.objects.get_or_create(
            username='teacher1',
            defaults={'email': 'teacher1@school.local', 'role': User.Role.TEACHER, 'first_name': 'Jane', 'last_name': 'Mwaura'},
        )
        if not teacher_user.has_usable_password():
            teacher_user.set_password('teacher123')
            teacher_user.save()

        teacher, _ = Teacher.objects.get_or_create(
            user=teacher_user,
            defaults={'employee_id': 'T-1001', 'department': 'Mathematics', 'qualification': 'B.Ed Mathematics'},
        )

        school_class, _ = SchoolClass.objects.get_or_create(
            name='Form 4',
            section='North',
            academic_year=year,
            defaults={'teacher': teacher},
        )

        subjects = [
            ('MAT101', 'Mathematics', teacher),
            ('ENG201', 'English', teacher),
            ('BIO301', 'Biology', teacher),
        ]

        created_subjects = []
        for code, title, subject_teacher in subjects:
            subject, _ = Subject.objects.get_or_create(
                code=code,
                defaults={'name': title, 'school_class': school_class, 'teacher': subject_teacher, 'description': f'{title} for {school_class}'},
            )
            created_subjects.append(subject)

        for index in range(1, 5):
            student_user, _ = User.objects.get_or_create(
                username=f'student{index}',
                defaults={'email': f'student{index}@school.local', 'role': User.Role.STUDENT, 'first_name': f'Student{index}', 'last_name': 'Demo'},
            )
            if not student_user.has_usable_password():
                student_user.set_password('student123')
                student_user.save()

            student, _ = Student.objects.get_or_create(
                user=student_user,
                defaults={'admission_number': f'SD-{1000 + index}', 'current_class': str(school_class), 'parent_name': 'Guardian Demo'},
            )

            Enrollment.objects.get_or_create(
                student=student,
                school_class=school_class,
                academic_year=year,
                term=term,
            )

            for subject in created_subjects:
                result, _ = Result.objects.get_or_create(
                    student=student,
                    subject=subject,
                    academic_year=year,
                    term=term,
                    assessment_type='CAT 1',
                    defaults={'marks': Decimal(70 + index * 5), 'entered_by': teacher_user, 'status': Result.ResultStatus.APPROVED},
                )
                result.grade = Result.calculate_grade(result.marks)
                result.save(update_fields=['marks', 'grade', 'status', 'entered_by'])

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
