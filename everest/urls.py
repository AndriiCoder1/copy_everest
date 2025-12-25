from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('partners.urls')),
    path('', include('memorials.urls')),
    path('', include('assets.urls')),
    path('', include('tributes.urls')),
    path('', include('shortlinks.urls')),
    path('', include('audits.urls')),
    path('', include('django_prometheus.urls')),
]

# ЭТО ТОЛЬКО ДЛЯ РАЗРАБОТКИ!
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)