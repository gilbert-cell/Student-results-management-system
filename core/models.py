from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        ADMIN = 'ADMIN', 'Admin'
        TEACHER = 'TEACHER', 'Teacher'
        STUDENT = 'STUDENT', 'Student'
        ACADEMIC_OFFICER = 'ACADEMIC_OFFICER', 'Head/Academic Officer'

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    phone_number = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        full_name = self.get_full_name() or self.username
        return f'{full_name} ({self.role})'

    def save(self, *args, **kwargs):
        if self.role == self.Role.SUPER_ADMIN or (self._state.adding and self.is_superuser):
            self.role = self.Role.SUPER_ADMIN
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = False
            self.is_superuser = False
        super().save(*args, **kwargs)


class Teacher(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_profile',
    )
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=80, blank=True)
    qualification = models.CharField(max_length=128, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.employee_id})'


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile',
    )
    admission_number = models.CharField(max_length=20, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True, default='')
    parent_name = models.CharField(max_length=120, blank=True, default='')
    current_class = models.CharField(max_length=80, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.admission_number})'


class AcademicYear(models.Model):
    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Term(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='terms',
    )
    name = models.CharField(max_length=40)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ('academic_year', 'name')

    def __str__(self):
        return f'{self.academic_year.name} - {self.name}'


class SchoolClass(models.Model):
    name = models.CharField(max_length=80)
    section = models.CharField(max_length=40, blank=True, default='')
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='classes',
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classes_assigned',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'section', 'academic_year')

    def __str__(self):
        if self.section:
            return f'{self.name} {self.section}'
        return self.name


class Subject(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        related_name='subjects',
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects_taught',
    )
    description = models.TextField(blank=True, default='')

    def __str__(self):
        return f'{self.code} - {self.name}'


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='enrollments')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='enrollments')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('student', 'school_class', 'academic_year', 'term')

    def __str__(self):
        return f'{self.student} -> {self.school_class}'


class Result(models.Model):
    class ResultStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        APPROVED = 'APPROVED', 'Approved'
        RETURNED = 'RETURNED', 'Returned for Correction'
        PUBLISHED = 'PUBLISHED', 'Published'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='results')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='results')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='results')
    assessment_type = models.CharField(max_length=40, default='CAT')
    marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    grade = models.CharField(max_length=4, blank=True, default='', editable=False)
    remarks = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=ResultStatus.choices,
        default=ResultStatus.DRAFT,
    )
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='results_entered',
        null=True,
        blank=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='results_approved',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.grade = self.calculate_grade(self.marks)
        super().save(*args, **kwargs)

    @staticmethod
    def calculate_grade(marks):
        if marks >= 80:
            return 'A'
        if marks >= 70:
            return 'B'
        if marks >= 60:
            return 'C'
        if marks >= 50:
            return 'D'
        if marks >= 40:
            return 'E'
        return 'F'

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('student', 'subject', 'academic_year', 'term', 'assessment_type'),
                name='unique_student_subject_assessment',
            ),
            models.CheckConstraint(
                condition=models.Q(marks__gte=0) & models.Q(marks__lte=100),
                name='result_marks_between_0_and_100',
            ),
        ]
        indexes = [
            models.Index(fields=('status', '-created_at'), name='result_status_created_idx'),
            models.Index(fields=('student', 'term'), name='result_student_term_idx'),
        ]

    def __str__(self):
        return f'{self.student} - {self.subject} ({self.grade})'


class ResultApproval(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name='approvals')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_records',
    )
    decision = models.CharField(max_length=20, default='APPROVED')
    comments = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.result} - {self.decision}'


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=80)
    model_name = models.CharField(max_length=80)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.action} - {self.model_name}'
