from django.contrib import admin
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


class ReadOnlyRecordsAdmin(admin.ModelAdmin):
    """Keep workflow history and logged results immutable in Django admin."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

admin.site.register(User)
admin.site.register(Student)
admin.site.register(Teacher)
@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        list(AcademicYear.objects.select_for_update().values_list('pk', flat=True))
        if obj.is_active:
            AcademicYear.objects.exclude(pk=obj.pk).filter(is_active=True).update(is_active=False)
        super().save_model(request, obj, form, change)
        AuditLog.objects.create(
            actor=request.user,
            action='UPDATE' if change else 'CREATE',
            model_name='AcademicYear',
            description=f'{"Updated" if change else "Created"} academic year {obj.name} ({obj.pk}).',
        )
admin.site.register(Term)
admin.site.register(SchoolClass)
admin.site.register(Subject)
admin.site.register(Enrollment)
admin.site.register(Result, ReadOnlyRecordsAdmin)
admin.site.register(ResultApproval, ReadOnlyRecordsAdmin)
admin.site.register(AuditLog, ReadOnlyRecordsAdmin)
