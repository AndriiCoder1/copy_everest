from django.conf import settings
from django.utils import translation

class DisableCSRFMiddleware:
    """Middleware to disable CSRF check (ONLY for development!)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Временно помечаем запрос как не требующий проверки CSRF
        setattr(request, '_dont_enforce_csrf_checks', True)
        response = self.get_response(request)
        return response
