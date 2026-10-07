import json
import secrets
from datetime import timedelta
from json import JSONDecodeError

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import User

PASSWORD_RESET_TIMEOUT = 3600  # 1 hour
_SAFE_RESPONSE = {'detail': 'If that email address is registered, a reset link has been sent.'}


def user_payload(user):
    return {
        'id': user.pk,
        'username': user.get_username(),
        'name': user.get_full_name() or user.get_username(),
        'role': user.role,
    }


@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    return JsonResponse({'csrfToken': get_token(request)})


@require_POST
def login_view(request):
    try:
        payload = json.loads(request.body)
    except (JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Invalid login request.'}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({'detail': 'Invalid login request.'}, status=400)

    username = payload.get('username')
    password = payload.get('password')
    if not all(isinstance(value, str) and value for value in (username, password)):
        return JsonResponse({'detail': 'Username and password are required.'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({'detail': 'Invalid username or password.'}, status=401)

    login(request, user)
    return JsonResponse({'user': user_payload(user)})


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({'detail': 'Logged out.'})


@require_GET
def current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication credentials were not provided.'}, status=401)
    return JsonResponse({'user': user_payload(request.user)})


@require_POST
def forgot_password(request):
    try:
        payload = json.loads(request.body)
    except (JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Invalid request.'}, status=400)
    email = payload.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'detail': 'Email address is required.'}, status=400)

    try:
        user = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        return JsonResponse(_SAFE_RESPONSE)

    token = secrets.token_urlsafe(32)
    cache.set(f'pwd_reset_{token}', user.pk, PASSWORD_RESET_TIMEOUT)

    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    reset_link = f'{frontend_url}?reset_token={token}'
    school_name = getattr(settings, 'SCHOOL_NAME', '') or 'SRMS'

    send_mail(
        subject=f'{school_name} – Password reset request',
        message=(
            f'Hello {user.get_full_name() or user.get_username()},\n\n'
            f'A password reset was requested for your account.\n\n'
            f'Click the link below to set a new password (valid for 1 hour):\n'
            f'{reset_link}\n\n'
            f'If you did not request this, you can safely ignore this email.\n\n'
            f'{school_name}'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@srms.local'),
        recipient_list=[user.email],
        fail_silently=True,
    )
    return JsonResponse(_SAFE_RESPONSE)


@require_POST
def reset_password(request):
    try:
        payload = json.loads(request.body)
    except (JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Invalid request.'}, status=400)
    token = payload.get('token', '').strip()
    new_password = payload.get('new_password', '')
    if not token or not new_password:
        return JsonResponse({'detail': 'Token and new password are required.'}, status=400)

    user_pk = cache.get(f'pwd_reset_{token}')
    if not user_pk:
        return JsonResponse({'detail': 'This reset link is invalid or has expired.'}, status=400)

    try:
        user = User.objects.get(pk=user_pk, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'detail': 'This reset link is invalid or has expired.'}, status=400)

    try:
        validate_password(new_password, user=user)
    except ValidationError as error:
        return JsonResponse({'detail': ' '.join(error.messages)}, status=400)

    user.set_password(new_password)
    user.save(update_fields=['password'])
    cache.delete(f'pwd_reset_{token}')
    return JsonResponse({'detail': 'Your password has been reset. You can now sign in.'})


@require_POST
def change_password(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication credentials were not provided.'}, status=401)
    try:
        payload = json.loads(request.body)
    except (JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Invalid password change request.'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'detail': 'Invalid password change request.'}, status=400)

    current_password = payload.get('current_password')
    new_password = payload.get('new_password')
    if not isinstance(current_password, str) or not isinstance(new_password, str):
        return JsonResponse({'detail': 'Current and new passwords are required.'}, status=400)
    if not request.user.check_password(current_password):
        return JsonResponse({'detail': 'Current password is incorrect.'}, status=400)
    try:
        validate_password(new_password, user=request.user)
    except ValidationError as error:
        return JsonResponse({'detail': ' '.join(error.messages)}, status=400)

    request.user.set_password(new_password)
    request.user.save(update_fields=['password'])
    update_session_auth_hash(request, request.user)
    return JsonResponse({'detail': 'Password updated successfully.'})
