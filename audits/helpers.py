from .models import AuditLog
from .decorators import get_web_audit_context

def log_web_action(action, target_type, target_id, **metadata):
    """Add log entry for web action with family context"""
    context = get_web_audit_context()
    
    if context.get('family_token'):
        metadata['token_preview'] = context['token_preview']
        if context.get('family_invite_id'):
            metadata['family_invite_id'] = context['family_invite_id']
            metadata['family_email'] = context['family_email']
    
    return AuditLog.objects.create(
        actor_type=context.get('actor_type', 'system'),
        actor_id=context.get('actor_id'),
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata
    )