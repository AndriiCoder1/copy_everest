from .models import AuditLog
import threading

class AuditManager:
    """Простой менеджер для аудита без сигналов"""
    
    @staticmethod
    def log_action(action, target_type, target_id, request=None, **metadata):
        """Логирует действие вручную"""
        actor_type = 'system'
        actor_id = None
        
        if request:
            # Проверяем семейный токен
            token = request.GET.get('token') or request.headers.get('X-Family-Token')
            if token:
                actor_type = 'family'
                metadata['token_preview'] = f"{token[:8]}..." if len(token) > 8 else token
                # Находим FamilyInvite
                try:
                    from memorials.models import FamilyInvite
                    invite = FamilyInvite.objects.get(token=token)
                    metadata['family_invite_id'] = invite.id
                    metadata['family_email'] = invite.email
                except:
                    pass
            # Проверяем партнера
            elif request.user.is_authenticated:
                if hasattr(request.user, 'partneruser'):
                    actor_type = 'partner_user'
                    actor_id = request.user.id
                elif request.user.is_superuser:
                    actor_type = 'superuser'
                    actor_id = request.user.id
        
        return AuditLog.objects.create(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata
        )

# Использование:
# from audits.manager import AuditManager
# AuditManager.log_action('upload_media', 'media', asset.id, request)