from django.utils import translation
from django.conf import settings
from django.utils.translation.trans_real import _translations

class DisableCSRFMiddleware:
    """Middleware to disable CSRF check (ONLY for development!)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Временно помечаем запрос как не требующий проверки CSRF
        setattr(request, '_dont_enforce_csrf_checks', True)
        response = self.get_response(request)
        return response


class ForceJSI18nMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Если это запрос к jsi18n
        if '/jsi18n/' in request.path:
            # Принудительно очищаем кэш переводов
            language = request.GET.get('language', translation.get_language())
            key = (language, 'djangojs')
            if key in _translations:
                del _translations[key]
                print(f"=== Cleared djangojs cache for {language} ===")
        
        return response        


class ForceLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Получаем язык из параметра
        lang = request.GET.get('language')
        
        # Также проверяем сессию (на случай если язык уже установлен)
        if not lang and hasattr(request, 'session'):
            lang = request.session.get('django_language')
        
        if lang and lang in ['de', 'en', 'fr', 'it']:
            # 1. Сохраняем в сессии
            request.session['django_language'] = lang
            request.session.modified = True
            
            # 2. Активируем язык для этого запроса
            from django.utils import translation
            translation.activate(lang)
            request.LANGUAGE_CODE = translation.get_language()
            
            print(f"LANG MIDDLEWARE: Язык {lang} активирован")
        
        response = self.get_response(request)
        
        return response