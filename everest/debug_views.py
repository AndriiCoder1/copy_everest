from django.http import JsonResponse
from django.utils.translation import get_language, activate, trans_real
import os

def debug_admin_i18n(request):
    import django.utils.translation as trans
    import django.utils.translation.trans_real as trans_real
    
    # Собираем ВСЮ информацию
    info = {
        'request.GET.language': request.GET.get('language'),
        'request.LANGUAGE_CODE': getattr(request, 'LANGUAGE_CODE', 'NOT SET'),
        'request._force_language': getattr(request, '_force_language', 'NOT SET'),
        'translation.get_language()': trans.get_language(),
        'session_language': request.session.get('django_language'),
        'cookie_language': request.COOKIES.get('django_language'),
        'djangojs_cache_keys': [str(k) for k in trans_real._translations.keys() 
                                if isinstance(k, tuple) and k[1] == 'djangojs'],
        'ALL_cache_keys': [str(k) for k in trans_real._translations.keys()],
        'request.META.HTTP_ACCEPT_LANGUAGE': request.META.get('HTTP_ACCEPT_LANGUAGE'),
    }
    
    # Выводим в консоль для отладки
    print("=" * 60)
    print("DEBUG VIEW - ПОЛНАЯ ИНФОРМАЦИЯ:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    print("=" * 60)
    
    return JsonResponse(info)