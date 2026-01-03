from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.utils.translation import activate, get_language

@never_cache
#@login_required
def force_admin_language(request):
    """Принудительно устанавливает язык и обновляет сессию"""
    from django.utils.translation import activate
    from django.shortcuts import redirect
    
    lang = request.GET.get('lang', 'de')
    
    if lang in ['de', 'en', 'fr', 'it']:
        # Активируем язык
        activate(lang)
        
        # Сохраняем в сессии
        if hasattr(request, 'session'):
            request.session['django_language'] = lang
            request.session.modified = True
            print(f"FORCE: Язык {lang} установлен и сессия сохранена")
        
        # Редирект в админку
        return redirect('/admin/')
    
    return redirect('/admin/')

def set_language_and_go_to_admin(request):
    """Устанавливает язык и переходит в админку"""
    lang = request.GET.get('lang', 'de')
    
    if lang in ['de', 'en', 'fr', 'it']:
        # Сохраняем в сессии
        request.session['django_language'] = lang
        request.session.modified = True
        
        # Устанавливаем куку
        from django.conf import settings
        response = redirect('/admin/')
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            lang,
            max_age=365*24*60*60,
            path=settings.LANGUAGE_COOKIE_PATH,
        )
        
        print(f"LANG SET: Язык {lang} установлен")
        return response
    
    return redirect('/admin/')    
