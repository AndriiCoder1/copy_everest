from django.conf import settings
from django.utils import translation
from django.contrib.auth import logout

class DisableCSRFMiddleware:
    """Middleware to disable CSRF check (ONLY for development!)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Временно помечаем запрос как не требующий проверки CSRF
        setattr(request, '_dont_enforce_csrf_checks', True)
        response = self.get_response(request)
        return response

class ForceLogoutForFamilyAccess:
    """ЛЕГКИЙ middleware: принудительно разлогинивает при семейном доступе"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Проверяем семейный токен
        has_token = 'token=' in request.META.get('QUERY_STRING', '')
        
        if has_token and request.user.is_authenticated:
            # Дополнительная проверка: это веб-интерфейс семьи, а не API
            if '/family/' in request.path:
                print(f"SECURITY: Logging out {request.user} for family web interface")
                logout(request)
        
        return self.get_response(request)