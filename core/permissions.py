from rest_framework.permissions import BasePermission

from .models import User


class RolePermission(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsAdmin(RolePermission):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN)


class IsSuperAdmin(RolePermission):
    allowed_roles = (User.Role.SUPER_ADMIN,)


class IsAdminOrAcademicOfficer(RolePermission):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.ACADEMIC_OFFICER)


class IsAnySystemRole(RolePermission):
    allowed_roles = tuple(role for role, _ in User.Role.choices)


class IsAdminOrTeacher(RolePermission):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.TEACHER)


class IsAcademicManagerOrTeacher(RolePermission):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.ACADEMIC_OFFICER, User.Role.TEACHER)


class IsAcademicManagerTeacherOrStudent(RolePermission):
    allowed_roles = tuple(role for role, _ in User.Role.choices)


# Roles that may review results (move to UNDER_REVIEW, APPROVED, or RETURNED)
class IsReviewer(RolePermission):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.ACADEMIC_OFFICER)


# Only Admin/SuperAdmin may publish approved results
class IsPublisher(RolePermission):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN)


class IsResultReader(RolePermission):
    allowed_roles = tuple(role for role, _ in User.Role.choices)

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method == 'POST':
            return request.user.role in (
                User.Role.SUPER_ADMIN,
                User.Role.ADMIN,
                User.Role.TEACHER,
            )
        return request.method == 'GET'


class IsResultEditor(RolePermission):
    allowed_roles = (
        User.Role.SUPER_ADMIN,
        User.Role.ADMIN,
        User.Role.TEACHER,
        User.Role.ACADEMIC_OFFICER,
    )
