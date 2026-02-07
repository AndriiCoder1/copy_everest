from django.shortcuts import render
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class HealthCheckView(APIView):
    permission_classes = []
    
    def get(self, request):
        checks = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
        }
        
        # Проверка базы данных
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks['database'] = 'ok'
        except Exception as e:
            checks['database'] = f'error: {str(e)}'
            checks['status'] = 'degraded'
        
        # Проверка Celery (только если настроен брокер)
        try:
            from celery import current_app
            insp = current_app.control.inspect()
            if insp:
                checks['celery'] = 'ok' 
            else:
                checks['celery'] = 'no_workers'
        except Exception as e:
            checks['celery'] = f'error: {str(e)}'
        
        # Проверка хранилища (если настроено S3)
        try:
            from django.core.files.storage import default_storage
            default_storage.exists('test.txt')
            checks['storage'] = 'ok'
        except Exception as e:
            checks['storage'] = f'error: {str(e)}'
        
        return Response(checks)
def debug_i18n(request):
    """Translation download debug page"""
    return render(request, 'debug_i18n.html')
