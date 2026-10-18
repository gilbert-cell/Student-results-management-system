from django.http import JsonResponse


class RequirePasswordChangeMiddleware:
    """Restrict first-login accounts to password-change and session endpoints."""

    allowed_paths = {
        '/api/auth/change-password/',
        '/api/auth/csrf/',
        '/api/auth/logout/',
        '/api/auth/me/',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (
            user and user.is_authenticated and user.must_change_password
            and request.path.startswith('/api/') and request.path not in self.allowed_paths
        ):
            return JsonResponse({'detail': 'Change your temporary password before continuing.', 'must_change_password': True}, status=403)
        return self.get_response(request)
