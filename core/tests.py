from decimal import Decimal

from django.test import Client
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import (
    AcademicYear,
    AuditLog,
    Enrollment,
    Result,
    SchoolClass,
    Student,
    Subject,
    Teacher,
    Term,
    User,
)


class RoleAuthenticationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password='admin-password',
            role=User.Role.ADMIN,
        )
        self.officer = User.objects.create_user(
            username='officer',
            password='officer-password',
            role=User.Role.ACADEMIC_OFFICER,
        )
        self.teacher_user = User.objects.create_user(
            username='teacher',
            password='teacher-password',
            role=User.Role.TEACHER,
            first_name='Jane',
            last_name='Teacher',
        )
        self.student_user = User.objects.create_user(
            username='student',
            password='student-password',
            role=User.Role.STUDENT,
        )

        self.teacher = Teacher.objects.create(user=self.teacher_user, employee_id='T-100')
        self.student = Student.objects.create(user=self.student_user, admission_number='S-100')
        self.year = AcademicYear.objects.create(
            name='2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            is_active=True,
        )
        self.term = Term.objects.create(
            academic_year=self.year,
            name='Term 1',
            start_date='2026-01-01',
            end_date='2026-04-30',
            is_active=True,
        )
        self.school_class = SchoolClass.objects.create(
            name='Form 1',
            academic_year=self.year,
            teacher=self.teacher,
        )
        self.subject = Subject.objects.create(
            code='MAT101',
            name='Mathematics',
            school_class=self.school_class,
            teacher=self.teacher,
        )
        Enrollment.objects.create(
            student=self.student,
            school_class=self.school_class,
            academic_year=self.year,
            term=self.term,
        )
        self.submitted_result = Result.objects.create(
            student=self.student,
            subject=self.subject,
            academic_year=self.year,
            term=self.term,
            marks=Decimal('78'),
            status=Result.ResultStatus.SUBMITTED,
            entered_by=self.teacher_user,
        )

    def authenticate_as(self, user):
        self.client.force_authenticate(user=user)

    def test_protected_api_rejects_anonymous_requests(self):
        response = self.client.get('/api/dashboard/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_teacher_sees_only_assigned_classes_and_cannot_manage_them(self):
        self.authenticate_as(self.teacher_user)

        classes_response = self.client.get('/api/classes/')
        create_response = self.client.post('/api/classes/', {}, format='json')

        self.assertEqual(classes_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in classes_response.data], [self.school_class.id])
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_sees_only_own_published_results_and_profile(self):
        own_approved_result = Result.objects.create(
            student=self.student,
            subject=self.subject,
            academic_year=self.year,
            term=self.term,
            assessment_type='Final Exam',
            marks=Decimal('88'),
            status=Result.ResultStatus.PUBLISHED,
            entered_by=self.teacher_user,
        )
        unpublished_result = Result.objects.create(
            student=self.student,
            subject=self.subject,
            academic_year=self.year,
            term=self.term,
            assessment_type='Unpublished Exam',
            marks=Decimal('99'),
            status=Result.ResultStatus.APPROVED,
            entered_by=self.teacher_user,
        )
        other_user = User.objects.create_user(
            username='other-student',
            password='other-password',
            role=User.Role.STUDENT,
        )
        other_student = Student.objects.create(user=other_user, admission_number='S-200')
        Result.objects.create(
            student=other_student,
            subject=self.subject,
            academic_year=self.year,
            term=self.term,
            marks=Decimal('95'),
            status=Result.ResultStatus.PUBLISHED,
            entered_by=self.teacher_user,
        )
        self.authenticate_as(self.student_user)

        results_response = self.client.get('/api/results/')
        profile_response = self.client.get('/api/my/profile/')

        self.assertEqual(results_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in results_response.data], [own_approved_result.id])
        self.assertNotIn(unpublished_result.id, [item['id'] for item in results_response.data])
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data['admission_number'], self.student.admission_number)

    def test_teacher_can_enter_results_for_assigned_subject_and_student(self):
        self.authenticate_as(self.teacher_user)

        response = self.client.post('/api/results/', {
            'student_id': self.student.id,
            'subject_id': self.subject.id,
            'academic_year_id': self.year.id,
            'term_id': self.term.id,
            'assessment_type': 'CAT 2',
            'marks': '82',
            'status': Result.ResultStatus.SUBMITTED,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_result = Result.objects.get(pk=response.data['id'])
        self.assertEqual(created_result.entered_by, self.teacher_user)
        self.assertEqual(created_result.status, Result.ResultStatus.SUBMITTED)

    def test_teacher_cannot_enter_results_for_another_teachers_subject(self):
        other_teacher_user = User.objects.create_user(
            username='other-teacher',
            password='other-password',
            role=User.Role.TEACHER,
        )
        other_teacher = Teacher.objects.create(user=other_teacher_user, employee_id='T-200')
        other_subject = Subject.objects.create(
            code='ENG201',
            name='English',
            school_class=self.school_class,
            teacher=other_teacher,
        )
        self.authenticate_as(self.teacher_user)

        response = self.client.post('/api/results/', {
            'student_id': self.student.id,
            'subject_id': other_subject.id,
            'academic_year_id': self.year.id,
            'term_id': self.term.id,
            'assessment_type': 'CAT 2',
            'marks': '82',
            'status': Result.ResultStatus.SUBMITTED,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_academic_officer_reviews_then_approves_and_cannot_edit_approved_marks(self):
        self.authenticate_as(self.officer)

        review_response = self.client.patch(
            f'/api/results/{self.submitted_result.id}/',
            {'status': Result.ResultStatus.UNDER_REVIEW},
            format='json',
        )
        response = self.client.patch(
            f'/api/results/{self.submitted_result.id}/',
            {'status': Result.ResultStatus.APPROVED},
            format='json',
        )

        self.assertEqual(review_response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.submitted_result.refresh_from_db()
        self.assertEqual(self.submitted_result.status, Result.ResultStatus.APPROVED)
        self.assertEqual(self.submitted_result.approved_by, self.officer)

        invalid_response = self.client.patch(
            f'/api/results/{self.submitted_result.id}/',
            {'marks': 100},
            format='json',
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_administrator_cannot_edit_or_reopen_approved_or_published_results(self):
        self.authenticate_as(self.admin)
        self.submitted_result.status = Result.ResultStatus.PUBLISHED
        self.submitted_result.save()

        edit_response = self.client.patch(
            f'/api/results/{self.submitted_result.id}/', {'marks': 100}, format='json',
        )
        reopen_response = self.client.patch(
            f'/api/results/{self.submitted_result.id}/', {'status': Result.ResultStatus.DRAFT}, format='json',
        )

        self.assertEqual(edit_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(reopen_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.submitted_result.refresh_from_db()
        self.assertEqual(self.submitted_result.marks, Decimal('78'))
        self.assertEqual(self.submitted_result.status, Result.ResultStatus.PUBLISHED)

    def test_administrators_cannot_create_results_that_skip_the_review_workflow(self):
        self.authenticate_as(self.admin)

        response = self.client.post('/api/results/', {
            'student_id': self.student.id,
            'subject_id': self.subject.id,
            'academic_year_id': self.year.id,
            'term_id': self.term.id,
            'assessment_type': 'Final Exam',
            'marks': '82',
            'status': Result.ResultStatus.PUBLISHED,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Result.objects.filter(assessment_type='Final Exam').exists())

    def test_admin_cannot_grant_elevated_roles(self):
        self.authenticate_as(self.admin)
        response = self.client.post('/api/users/', {
            'username': 'new-admin',
            'password': 'a-safe-password',
            'role': User.Role.SUPER_ADMIN,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username='new-admin').exists())

    def test_super_admin_can_create_and_update_user_accounts(self):
        root = User.objects.create_user(
            username='root-admin', password='root-password', role=User.Role.SUPER_ADMIN,
        )
        self.authenticate_as(root)

        created = self.client.post('/api/users/', {
            'username': 'new-admin',
            'password': 'a-safe-password',
            'role': User.Role.SUPER_ADMIN,
            'email': 'admin@school.local',
        }, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        account = User.objects.get(username='new-admin')
        self.assertTrue(account.check_password('a-safe-password'))
        self.assertTrue(account.is_staff)
        self.assertTrue(account.is_superuser)

        updated = self.client.patch(
            f'/api/users/{account.pk}/',
            {'first_name': 'School', 'role': User.Role.TEACHER, 'password': 'new-password'},
            format='json',
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        account.refresh_from_db()
        self.assertEqual(account.first_name, 'School')
        self.assertEqual(account.role, User.Role.TEACHER)
        self.assertTrue(account.check_password('new-password'))
        self.assertFalse(account.is_staff)
        self.assertFalse(account.is_superuser)

    def test_only_super_admin_can_change_user_status_and_cannot_disable_self(self):
        target = User.objects.create_user(
            username='status-target', password='target-password', role=User.Role.TEACHER,
        )
        self.authenticate_as(self.admin)
        denied = self.client.patch(
            f'/api/users/{target.pk}/', {'is_active': False}, format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        target.refresh_from_db()
        self.assertTrue(target.is_active)

        root = User.objects.create_user(
            username='root-admin', password='root-password', role=User.Role.SUPER_ADMIN,
        )
        self.authenticate_as(root)
        self_response = self.client.patch(
            f'/api/users/{root.pk}/', {'is_active': False}, format='json',
        )
        self.assertEqual(self_response.status_code, status.HTTP_400_BAD_REQUEST)
        demote_self_response = self.client.patch(
            f'/api/users/{root.pk}/', {'role': User.Role.ADMIN}, format='json',
        )
        self.assertEqual(demote_self_response.status_code, status.HTTP_400_BAD_REQUEST)
        root.refresh_from_db()
        self.assertEqual(root.role, User.Role.SUPER_ADMIN)
        self.assertTrue(root.is_active)

    def test_super_admin_role_is_the_only_django_superuser_role(self):
        super_admin = User.objects.create_user(
            username='root-admin',
            password='root-password',
            role=User.Role.SUPER_ADMIN,
        )
        self.assertTrue(super_admin.is_staff)
        self.assertTrue(super_admin.is_superuser)
        self.assertFalse(self.admin.is_staff)
        self.assertFalse(self.admin.is_superuser)

    def test_only_super_admin_can_disable_accounts_and_action_is_audited(self):
        target = User.objects.create_user(
            username='disable-me', password='target-password', role=User.Role.TEACHER,
        )
        self.authenticate_as(self.admin)
        denied = self.client.delete(f'/api/users/{target.id}/')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        target.refresh_from_db()
        self.assertTrue(target.is_active)

        root = User.objects.create_user(
            username='root-admin', password='root-password', role=User.Role.SUPER_ADMIN,
        )
        self.authenticate_as(root)
        disabled = self.client.delete(f'/api/users/{target.id}/')
        self.assertEqual(disabled.status_code, status.HTTP_204_NO_CONTENT)
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertTrue(AuditLog.objects.filter(actor=root, action='DISABLE', model_name='User').exists())

    def test_student_list_is_scoped_to_the_current_student(self):
        second_user = User.objects.create_user(
            username='second-student',
            password='student-password',
            role=User.Role.STUDENT,
        )
        Student.objects.create(user=second_user, admission_number='S-200')
        self.authenticate_as(self.student_user)
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['admission_number'] for item in response.data], ['S-100'])

    def test_teacher_roster_is_limited_to_assigned_subject_enrolments(self):
        other_user = User.objects.create_user(
            username='other-student', password='student-password', role=User.Role.STUDENT,
        )
        other_student = Student.objects.create(user=other_user, admission_number='S-300')
        other_teacher_user = User.objects.create_user(
            username='other-teacher', password='teacher-password', role=User.Role.TEACHER,
        )
        other_teacher = Teacher.objects.create(user=other_teacher_user, employee_id='T-300')
        other_class = SchoolClass.objects.create(name='Form 2', academic_year=self.year, teacher=other_teacher)
        other_subject = Subject.objects.create(
            code='ENG302', name='English', school_class=other_class, teacher=other_teacher,
        )
        Enrollment.objects.create(
            student=other_student, school_class=other_class, academic_year=self.year, term=self.term,
        )
        self.authenticate_as(self.teacher_user)
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['admission_number'] for item in response.data], ['S-100'])
        self.assertNotIn('parent_name', response.data[0])

    def test_class_teacher_can_view_students_in_assigned_class_without_subject_assignment(self):
        class_only_student_user = User.objects.create_user(
            username='class-only-student', password='student-password', role=User.Role.STUDENT,
        )
        class_only_student = Student.objects.create(
            user=class_only_student_user, admission_number='S-400',
        )
        assigned_class = SchoolClass.objects.create(
            name='Form 2', academic_year=self.year, teacher=self.teacher,
        )
        Enrollment.objects.create(
            student=class_only_student,
            school_class=assigned_class,
            academic_year=self.year,
            term=self.term,
        )
        self.authenticate_as(self.teacher_user)

        response = self.client.get('/api/students/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item['admission_number'] for item in response.data}, {'S-100', 'S-400'},
        )

    def test_admin_can_create_users_with_hashed_passwords(self):
        self.authenticate_as(self.admin)

        response = self.client.post('/api/users/', {
            'username': 'new-teacher',
            'password': 'a-safe-password',
            'role': User.Role.TEACHER,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(username='new-teacher')
        self.assertTrue(created_user.check_password('a-safe-password'))

    def test_login_checks_csrf_and_uses_account_role(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/api/auth/csrf/')
        csrf_token_value = client.cookies['csrftoken'].value
        payload = {
            'username': self.teacher_user.username,
            'password': 'teacher-password',
        }

        missing_csrf = client.post(
            '/api/auth/login/',
            data=payload,
            content_type='application/json',
        )
        payload['password'] = 'wrong-password'
        rejected = client.post(
            '/api/auth/login/',
            data=payload,
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token_value,
        )
        payload['password'] = 'teacher-password'
        accepted = client.post(
            '/api/auth/login/',
            data=payload,
            content_type='application/json',
            HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value,
        )

        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()['user']['role'], User.Role.TEACHER)

    def test_teacher_can_view_own_profile_and_assignments_metadata(self):
        self.client.force_authenticate(user=self.teacher_user)

        response = self.client.get('/api/my/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['employee_id'], self.teacher.employee_id)
        self.assertEqual(response.data['full_name'], 'Jane Teacher')
        self.assertEqual(response.data['account']['username'], 'teacher')
        self.assertEqual(response.data['account']['role'], User.Role.TEACHER)
        self.assertTrue(response.data['account']['is_active'])
        self.assertIn('date_joined', response.data['account'])
        self.assertIn('last_login', response.data['account'])

    def test_user_can_change_password_and_keep_session(self):
        client = APIClient()
        self.assertTrue(client.login(username='teacher', password='teacher-password'))

        rejected = client.post('/api/auth/change-password/', {
            'current_password': 'incorrect-password',
            'new_password': 'N3w!Secure-Teacher-Password-2026',
        }, format='json')
        accepted = client.post('/api/auth/change-password/', {
            'current_password': 'teacher-password',
            'new_password': 'N3w!Secure-Teacher-Password-2026',
        }, format='json')
        still_authenticated = client.get('/api/auth/me/')

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.get(pk=self.teacher_user.pk).check_password('N3w!Secure-Teacher-Password-2026'))
        self.assertEqual(still_authenticated.status_code, status.HTTP_200_OK)
