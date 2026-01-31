import threading
from django.utils.deprecation import MiddlewareMixin
from memorials.models import FamilyInvite
from django.utils import timezone
from django.contrib.auth.middleware import get_user 

# Хранилище для текущего запроса (thread-safe)
_request_local = threading.local()

class AuditMiddleware(MiddlewareMixin):
    """Middleware для определения контекста запроса и аудита"""
    
    def process_request(self, request):

        current_user = get_user(request)
        # Сохраняем пользователя и запрос
        _request_local.user = current_user
        _request_local.request = request
        
        # Инициализируем контекст запроса
        request_context = {
            'is_family_access': False,
            'is_partner_access': False,
            'is_public_access': True,  
            'family_token': None,
            'family_invite_id': None,
            'actor_type': 'system',
            'actor_id': None,
        }
        
        # Определяем семейный доступ
        token = self._extract_token(request)
        if token:
            request_context.update({
                'actor_type': 'family',
                'is_family_access': True,
                'is_public_access': False,
                'family_token': token,
                'token_preview': f"{token[:8]}..." if len(token) > 8 else token,
            })
            
            # Пытаемся найти FamilyInvite
            try:
                invite = FamilyInvite.objects.get(
                    token=token,
                    expires_at__gt=timezone.now()
                )
                request_context['family_invite_id'] = invite.id
                request_context['family_email'] = invite.email
            except FamilyInvite.DoesNotExist:
                pass
        
        # Определяем партнерский доступ
        elif current_user.is_authenticated:
            request_context['is_public_access'] = False
            
            if hasattr(current_user, 'partneruser'):
                request_context.update({
                    'actor_type': 'partner_user',
                    'actor_id': current_user.id,
                    'is_partner_access': True,
                })
            elif current_user.is_superuser:
                request_context.update({
                    'actor_type': 'superuser',
                    'actor_id': current_user.id,
                    'is_admin_access': True,
                })
         # Гость (публичный доступ)
        elif request.path.startswith('/api/memorials/') and '/public/' in request.path:
            request_context.update({
                'actor_type': 'guest',
                'access_type': 'public'
            })
        # Сохраняем контекст
        _request_local.context = request_context
        request.audit_context = request_context  
    
    def _extract_token(self, request):
        """Извлекает токен из различных источников"""
        # 1. Из заголовка X-Family-Token
        token = request.headers.get('X-Family-Token')
        if token:
            return token
        
        # 2. Из GET параметров
        token = request.GET.get('token')
        if token:
            return token
        
        # 3. Из POST данных
        if request.method == 'POST':
            token = request.POST.get('token')
            if token:
                return token
        
        # 4. Из сессии (если ранее был установлен)
        token = request.session.get('family_token')
        if token:
            return token
        
        return None
    
    def process_response(self, request, response):
        # Очищаем thread-local storage
        for attr in ['user', 'request', 'context']:
            if hasattr(_request_local, attr):
                delattr(_request_local, attr)
        return response


def get_current_user():
    """Получить текущего пользователя"""
    return getattr(_request_local, 'user', None)


def get_current_request():
    """Получить текущий запрос"""
    return getattr(_request_local, 'request', None)


def get_request_context():
    """Получить контекст текущего запроса"""
    return getattr(_request_local, 'context', {})


def get_family_token():
    """Получить токен семьи из текущего контекста"""
    context = get_request_context()
    return context.get('family_token')


def is_family_access():
    """Проверяет, является ли текущий доступ семейным"""
    context = get_request_context()
    return context.get('is_family_access', False)


def is_partner_access():
    """Проверяет, является ли текущий доступ партнерским"""
    context = get_request_context()
    return context.get('is_partner_access', False)