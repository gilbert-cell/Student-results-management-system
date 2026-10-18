import secrets

from django.contrib.auth import get_user_model
from django.utils.text import slugify


User = get_user_model()


def student_username(first_name, last_name, exclude_user_id=None):
    base = slugify(f'{first_name}_{last_name}').replace('-', '_')[:140] or 'student'
    username = base
    suffix = 2
    existing = User.objects.filter(username=username)
    if exclude_user_id:
        existing = existing.exclude(pk=exclude_user_id)
    while existing.exists():
        ending = f'_{suffix}'
        username = f'{base[:150 - len(ending)]}{ending}'
        suffix += 1
        existing = User.objects.filter(username=username)
        if exclude_user_id:
            existing = existing.exclude(pk=exclude_user_id)
    return username


def issue_student_credentials(user):
    """Set a fresh, one-time password and require a change at first sign-in."""
    user.username = student_username(user.first_name, user.last_name, exclude_user_id=user.pk)
    temporary_password = secrets.token_urlsafe(12)
    user.set_password(temporary_password)
    user.is_active = True
    user.must_change_password = True
    user.save(update_fields=('username', 'password', 'is_active', 'must_change_password'))
    if hasattr(user, 'student_activation'):
        user.student_activation.delete()
    return {'username': user.username, 'temporary_password': temporary_password}


def create_student_user(*, first_name, last_name, email='', phone_number=''):
    user = User(
        username=student_username(first_name, last_name),
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        role=User.Role.STUDENT,
        is_active=True,
        must_change_password=True,
    )
    temporary_password = secrets.token_urlsafe(12)
    user.set_password(temporary_password)
    user.save()
    return user, {'username': user.username, 'temporary_password': temporary_password}
