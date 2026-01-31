import threading
from functools import wraps
from memorials.models import FamilyInvite

_web_context = threading.local()

def audit_family_view(view_func):
    """Декоратор для логирования действий в веб-интерфейсе семьи"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Устанавливаем контекст
        token = request.GET.get('token')
        context = {
            'actor_type': 'system',
            'actor_id': None,
            'family_token': token,
            'token_preview': f"{token[:8]}..." if token and len(token) > 8 else token,
        }
        
        if token:
            context['actor_type'] = 'family'
            try:
                invite = FamilyInvite.objects.get(token=token)
                context['family_invite_id'] = invite.id
                context['family_email'] = invite.email
            except FamilyInvite.DoesNotExist:
                pass
        
        _web_context.value = context
        
        try:
            return view_func(request, *args, **kwargs)
        finally:
            # Очищаем контекст
            if hasattr(_web_context, 'value'):
                delattr(_web_context, 'value')
    
    return wrapper

def get_web_audit_context():
    """Получает контекст для веб-интерфейса"""
    return getattr(_web_context, 'value', {})


