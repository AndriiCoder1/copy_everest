from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.http import HttpResponse
from django.utils.translation import gettext as _
from django.shortcuts import render, redirect
from django.views.i18n import JavaScriptCatalog
from django.views.decorators.cache import never_cache
from .views import force_admin_language
# ============ СУЩЕСТВУЮЩИЕ ФУНКЦИИ ============

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

def force_admin_language(request):
    """Принудительно устанавливает язык (без проверки авторизации)"""
    from django.utils.translation import activate
    
    lang = request.GET.get('lang', 'de')
    
    if lang in ['de', 'en', 'fr', 'it']:
        # Активируем язык
        activate(lang)
        
        # Сохраняем в сессии
        request.session['django_language'] = lang
        request.session.modified = True
        
        print(f"FORCE: Язык {lang} установлен и сессия сохранена")
        
        # Редирект в админку
        return redirect('/admin/')
    
    return redirect('/admin/')

def language_switcher(request):
    """Страница для переключения языка"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Switch Language</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .language-option { 
                display: block; 
                font-size: 24px; 
                margin: 20px 0; 
                padding: 10px; 
                text-decoration: none;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            .language-option:hover {
                background-color: #f0f0f0;
            }
        </style>
    </head>
    <body>
        <h1>Select Admin Language:</h1>
        <p>Выберите язык для админки:</p>
        <a href="/set-lang/?lang=de" class="language-option">🇩🇪 Deutsch</a>
        <a href="/set-lang/?lang=en" class="language-option">🇬🇧 English</a>
        <a href="/set-lang/?lang=fr" class="language-option">🇫🇷 Français</a>
        <a href="/set-lang/?lang=it" class="language-option">🇮🇹 Italiano</a>
        <hr>
        <p>После выбора языка вы будете перенаправлены в админку.</p>
        <p><small>Если не авторизованы, сначала войдите в систему.</small></p>
    </body>
    </html>
    """
    return HttpResponse(html)

# Простая тестовая view прямо здесь
def test_language_view(request):
    lang = request.GET.get('language', 'en')
    activate(lang)
    
    # Сохраняем в сессии
    if hasattr(request, 'session'):
        request.session['django_language'] = lang
    
    html = f"""
    <html><body>
        <h1>Language Test ({lang})</h1>
        <p>Memorial: {_('Memorial')}</p>
        <p>Save: {_('Save')}</p>
        <p>Delete: {_('Delete')}</p>
        <hr>
        <a href="?language=de">DE</a> | 
        <a href="?language=fr">FR</a> | 
        <a href="?language=it">IT</a> | 
        <a href="?language=en">EN</a>
        <hr>
        <a href="/admin/?language=de">Admin DE</a> | 
        <a href="/admin/?language=fr">Admin FR</a>
    </body></html>
    """
    response = HttpResponse(html)
    response.set_cookie('django_language', lang, max_age=365*24*60*60, path='/')
    return response

# Тест JavaScript i18n
def test_js_i18n(request):
    return render(request, 'simple_test.html')

# Простой JavaScript catalog
def simple_jsi18n(request):
    language = request.GET.get('language', 'de')
    
    translations = {
        'de': {
            'Cancel': 'Abbrechen',
            'Save': 'Sichern', 
            'Delete': 'Löschen',
            'Search': 'Suchen',
            'Add': 'Hinzufügen',
            'Change': 'Ändern',
            'Close': 'Schließen',
            'Yes': 'Ja',
            'No': 'Nein',
        },
        'fr': {
            'Cancel': 'Annuler',
            'Save': 'Enregistrer',
            'Delete': 'Supprimer',
            'Search': 'Rechercher',
            'Add': 'Ajouter',
            'Change': 'Modifier',
            'Close': 'Fermer',
            'Yes': 'Oui',
            'No': 'Non',
        },
        'it': {
            'Cancel': 'Annulla',
            'Save': 'Salva',
            'Delete': 'Cancella', 
            'Search': 'Cerca',
            'Add': 'Aggiungi',
            'Change': 'Modifica',
            'Close': 'Chiudi',
            'Yes': 'Sì',
            'No': 'No',
        }
    }
    
    lang_dict = translations.get(language, translations['de'])
    
    # Используем json.dumps для правильного форматирования
    import json
    catalog_json = json.dumps(lang_dict, ensure_ascii=False, indent=2)
    
    js_code = f"""'use strict';
{{
  const django = window.django || (window.django = {{}});
  
  django.catalog = {catalog_json};
  
  django.gettext = function(msgid) {{
    return django.catalog[msgid] || msgid;
  }};
  
  window.gettext = django.gettext;
}}
"""
    
    response = HttpResponse(js_code, content_type='application/javascript; charset=utf-8')
    return response

# ============ НОВЫЙ ФИНАЛЬНЫЙ ТЕСТ ============

def final_i18n_test(request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Final i18n Test</title>
        <meta charset="UTF-8">
        <style>
            .success { color: green; font-weight: bold; }
            .error { color: red; font-weight: bold; }
            .test { margin: 20px 0; padding: 10px; border: 1px solid #ccc; }
        </style>
        <script>
            function runAllTests() {
                console.clear();
                console.log('=== Starting all i18n tests ===');
                
                // Тест 1: Кастомные переводы
                testCustomTranslations();
                
                // Тест 2: Django Admin переводы (через публичный endpoint)
                setTimeout(testAdminTranslations, 500);
            }
            
            function testCustomTranslations() {
                console.log('Test 1: Custom translations...');
                const script = document.createElement('script');
                script.src = '/simple-jsi18n/?language=de';
                script.onload = function() {
                    if (window.django && django.catalog && django.catalog['Cancel'] === 'Abbrechen') {
                        console.log('✅ Custom translations: PASS');
                        document.getElementById('test1').innerHTML = 
                            '<span class="success">✅ PASS</span> - Custom translations work';
                    } else {
                        console.log('❌ Custom translations: FAIL');
                        document.getElementById('test1').innerHTML = 
                            '<span class="error">❌ FAIL</span> - Custom translations failed';
                    }
                };
                document.head.appendChild(script);
            }
            
            function testAdminTranslations() {
                console.log('Test 2: Django Admin translations...');
                fetch('/debug-admin-jsi18n/?language=de')
                    .then(response => response.text())
                    .then(jsCode => {
                        // Очищаем предыдущий django объект
                        if (window.django) window.django = undefined;
                        
                        eval(jsCode);
                        
                        if (window.django && django.catalog) {
                            const cancel = django.catalog['Cancel'];
                            console.log('Django Admin catalog keys:', Object.keys(django.catalog).length);
                            console.log('Cancel translation:', cancel);
                            
                            if (cancel && cancel !== 'Cancel') {
                                console.log('✅ Django Admin translations: PASS');
                                document.getElementById('test2').innerHTML = 
                                    `<span class="success">✅ PASS</span> - Django Admin translations work (Cancel: ${cancel})`;
                            } else {
                                console.log('❌ Django Admin translations: FAIL - Not translated');
                                document.getElementById('test2').innerHTML = 
                                    '<span class="error">❌ FAIL</span> - Django Admin translations not loaded';
                            }
                        } else {
                            console.log('❌ Django Admin translations: FAIL - No catalog');
                            document.getElementById('test2').innerHTML = 
                                '<span class="error">❌ FAIL</span> - No django.catalog created';
                        }
                    })
                    .catch(error => {
                        console.log('❌ Django Admin translations: FAIL - Network error');
                        document.getElementById('test2').innerHTML = 
                            `<span class="error">❌ FAIL</span> - Network error: ${error}`;
                    });
            }
            
            // Запускаем тесты при загрузке
            window.onload = runAllTests;
        </script>
    </head>
    <body>
        <h1>Final i18n Test</h1>
        
        <div class="test">
            <h2>Test 1: Custom JavaScript Translations</h2>
            <div id="test1">Running...</div>
        </div>
        
        <div class="test">
            <h2>Test 2: Django Admin JavaScript Translations</h2>
            <div id="test2">Running...</div>
        </div>
        
        <button onclick="runAllTests()">Run Tests Again</button>
        
        <h3>Summary:</h3>
        <p>If <strong>Test 1 PASSES</strong> but <strong>Test 2 FAILS</strong>, the issue is with Django Admin not loading your djangojs.mo files.</p>
        <p>If <strong>both PASS</strong>, your i18n setup is complete!</p>
    </body>
    </html>
    """
    return HttpResponse(html)

# ============ URL PATTERNS ============

urlpatterns = [
    # Тестовые пути
    path('set-lang/', set_language_and_go_to_admin, name='set_lang'),
    path('admin-force-lang/', force_admin_language, name='admin_force_lang'),
    path('switch-language/', language_switcher, name='language_switcher'),
    path('test-js-i18n/', test_js_i18n, name='test_js_i18n'),
    path('simple-jsi18n/', simple_jsi18n, name='simple_jsi18n'),
    path('final-test/', final_i18n_test, name='final_test'),
    path('debug-admin-jsi18n/', 
         never_cache(JavaScriptCatalog.as_view(
             packages=['django.contrib.admin', 'django.contrib.auth']
         )), 
         name='debug_admin_jsi18n'),
    
    # Существующие пути
    path('i18n/', include('django.conf.urls.i18n')),
    path('test-lang/', test_language_view, name='test-lang'),
    path('', include('partners.urls')),
    path('', include('memorials.urls')),
    path('', include('assets.urls')),
    path('', include('tributes.urls')),
    path('', include('shortlinks.urls')),
    path('', include('audits.urls')),
    path('', include('django_prometheus.urls')),
]

# i18n URL паттерны (для админки)
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    prefix_default_language=False,
)

# ЭТО ТОЛЬКО ДЛЯ РАЗРАБОТКИ!
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)