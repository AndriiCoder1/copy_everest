from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import JavaScriptCatalog
from django.shortcuts import render
from . import views

# ============ URL PATTERNS ============

urlpatterns = [
    # Standard i18n views (for language switching form)
    path('i18n/', include('django.conf.urls.i18n')),
    
    # JavaScript Catalog (accessible without prefix for convenience)
    path('jsi18n/', 
         JavaScriptCatalog.as_view(packages=['django.contrib.admin', 'django.contrib.auth']), 
         name='jsi18n'),

    # Debug view
    path('debug-i18n/', views.debug_i18n, name='debug_i18n'),

    # Apps (API endpoints - usually not prefixed, but can be if desired)
    path('', include('partners.urls')),
    path('', include('memorials.urls')),
    path('', include('assets.urls')),
    path('', include('tributes.urls')),
    path('', include('shortlinks.urls')),
    path('', include('audits.urls')),
    path('', include('django_prometheus.urls')),
]

# Admin with i18n patterns (adds /en/admin/, /fr/admin/, etc.)
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    # You can add other prefixed views here if needed
    prefix_default_language=True
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
