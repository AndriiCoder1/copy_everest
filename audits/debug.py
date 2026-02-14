import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'everest.settings')
import django
django.setup()

from django.test import RequestFactory
from audits.middleware import AuditMiddleware
from django.contrib.auth.models import User

def test_middleware():
    """Тестируем работу middleware"""
    print("=== TESTING MIDDLEWARE ===")
    
    factory = RequestFactory()
    
    # 1. Тест семейного доступа
    print("\n1. Family access test:")
    request = factory.get('/test/?token=IjJ3CGeqhH5VNHI37e4cD8SLx8lOyTnG')
    middleware = AuditMiddleware(lambda r: None)
    middleware.process_request(request)
    print(f"Context: {getattr(request, 'audit_context', 'NO CONTEXT')}")
    
    # 2. Тест партнерского доступа
    print("\n2. Partner access test:")
    request = factory.get('/test/')
    user = User.objects.get(username='1@bern.ch')
    request.user = user
    middleware.process_request(request)
    print(f"Context: {getattr(request, 'audit_context', 'NO CONTEXT')}")
    
    # 3. Тест публичного доступа
    print("\n3. Public access test:")
    request = factory.get('/api/memorials/REDE2020/')
    middleware.process_request(request)
    print(f"Context: {getattr(request, 'audit_context', 'NO CONTEXT')}")

def test_signals():
    """Тестируем работу сигналов"""
    print("\n=== TESTING SIGNALS ===")
    
    from memorials.models import Memorial
    from assets.models import MediaAsset
    
    # Создаем тестовый запрос
    factory = RequestFactory()
    request = factory.get('/test/?token=IjJ3CGeqhH5VNHI37e4cD8SLx8lOyTnG')
    
    # Устанавливаем контекст вручную
    from audits.middleware import _request_local
    _request_local.context = {
        'actor_type': 'family',
        'is_family_access': True,
        'family_token': 'IjJ3CGeqhH5VNHI37e4cD8SLx8lOyTnG',
        'token_preview': 'IjJ3CGeq...',
        'family_invite_id': 1,
    }
    
    print("Signal context set. Now test creating an object...")

if __name__ == '__main__':
    test_middleware()
    test_signals()