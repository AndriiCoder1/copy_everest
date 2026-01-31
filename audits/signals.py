from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import AuditLog
from memorials.models import Memorial, FamilyInvite
from tributes.models import Tribute
from assets.models import MediaAsset
from .middleware import get_current_user, get_request_context, get_family_token
from django.utils import timezone
from .middleware import get_current_user

# ЛОГИРОВАНИЕ АКТИВНОСТИ ПОЛЬЗОВАТЕЛЕЙ
def _get_actor_info():
    """Gets information about an actor from the current user"""
    from partners.models import PartnerUser
    user = get_current_user()
    
    # Значения по умолчанию
    actor_type = 'system'
    actor_id = 0
    
    if user and user.is_authenticated:
        # Проверяем, является ли пользователь суперпользователем
        if user.is_superuser:
            actor_type = 'admin'
            actor_id = user.id
        else:
            # Пытаемся найти связанный объект PartnerUser
            try:
                # Используем обратную связь от User к PartnerUser
                partner_user = PartnerUser.objects.get(email=user.email)
                actor_type = 'partner_user'
                actor_id = partner_user.id
            except PartnerUser.DoesNotExist:
                # Если PartnerUser не найден, значит это обычный пользователь Django
                actor_type = 'user'
                actor_id = user.id
    
    return actor_type, actor_id


@receiver(post_save, sender=Tribute)
def log_tribute_moderation(sender, instance, created, **kwargs):
    """Логирует создание и модерацию трибьютов"""
    
    # ⚠️ СНАЧАЛА ПРОВЕРЯЕМ ФЛАГ - РАННИЙ ВЫХОД ДЛЯ ОПТИМИЗАЦИИ
    if hasattr(instance, '_skip_audit_log'):
        # Эта модерация уже залогирована в views.py
        # Очищаем флаг, чтобы не мешал дальше
        del instance._skip_audit_log
        return

    # Получаем контекст
    context = get_request_context()
    
    # ЛОГИРОВАНИЕ СОЗДАНИЯ НОВОГО ТРИБУТА
    if created:
        # ⚠️ ВАЖНО: тоже проверяем флаг для создания (на всякий случай)
        if hasattr(instance, '_skip_audit_log'):
            del instance._skip_audit_log
            return
        actor_type, actor_id = _get_actor_info()
        metadata = {
            'memorial_id': instance.memorial.id,
            'memorial_code': instance.memorial.short_code,
            'author_name': instance.author_name,
            'initial_status': 'pending',
            'gdpr_relevant': True
        }
        
        if context.get('is_family_access'):
            # Гость через публичный доступ
            actor_type = 'guest'
            metadata['access_type'] = 'public'
            
        elif context.get('is_partner_access'):
            # Партнер через админку
            actor_type, actor_id = _get_actor_info()
            metadata['access_type'] = 'partner_admin'
        
        AuditLog.objects.create(
            actor_type=actor_type,
            actor_id=actor_id,
            action='create_tribute',
            target_type='tribute',
            target_id=instance.id,
            metadata=metadata
        )
        return
    
    # ЛОГИРОВАНИЕ МОДЕРАЦИИ
    if hasattr(instance, 'tracker') and instance.tracker.has_changed('status'):
        old_status = instance.tracker.previous('status')
        new_status = instance.status
        
        actor_type, actor_id = _get_actor_info()
        metadata = {
            'memorial_id': instance.memorial.id,
            'memorial_code': instance.memorial.short_code,
            'old_status': old_status,
            'new_status': new_status,
            'gdpr_relevant': True
        }
        
        if context.get('is_family_invite'):
            # Семья получила приглашение (например, через API)
            actor_type, actor_id = _get_actor_info()
            metadata['access_type'] = 'family_invite'
            
            family_token = get_family_token()
            
            if family_token:
                # Безопасно логируем (обрезанный токен)
                safe_token = family_token[:8] + '...' if len(family_token) > 8 else '***'
                
                # Пытаемся найти FamilyInvite для деталей
                try:
                    invite = FamilyInvite.objects.get(token=family_token)
                    metadata.update({
                        'family_invite_id': invite.id,
                        'family_email': invite.email,
                        'token_preview': safe_token,
                    })
                except FamilyInvite.DoesNotExist:
                    metadata['token_preview'] = safe_token
            
        elif context.get('is_partner_access'):
            # ПАРТНЕР одобрил через админку
            actor_type, actor_id = _get_actor_info()
            metadata['access_type'] = 'partner_admin'
            
        elif instance.moderated_by_user:
            # Партнер через API или другую систему
            actor_type, actor_id = _get_actor_info()
            metadata['access_type'] = 'api_or_system'
        
        AuditLog.objects.create(
            actor_type=actor_type,
            actor_id=actor_id,
            action='moderate_tribute',
            target_type='tribute',
            target_id=instance.id,
            metadata=metadata
        )


@receiver(post_save, sender=Memorial)
def log_memorial_change(sender, instance, created, **kwargs):
    """Логирует изменения мемориалов"""
    action = 'create_memorial' if created else 'update_memorial'
    
    context = get_request_context()
    
    actor_type, actor_id = _get_actor_info()
    metadata = {
        'memorial_id': instance.id,
        'short_code': instance.short_code,
    }
    
    if context.get('is_partner_access'):
        actor_type, actor_id = _get_actor_info()
        metadata['access_type'] = 'partner_admin'
    
    AuditLog.objects.create(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type='memorial',
        target_id=instance.id,
        metadata=metadata
    )


@receiver(post_save, sender=MediaAsset)
def log_media_access(sender, instance, created, **kwargs):
    """Логирует загрузку медиа-файлов"""
    if not created:
        return
    
    context = get_request_context()
    
    actor_type, actor_id = _get_actor_info()
    metadata = {
        'memorial_id': instance.memorial.id,
        'file_type': instance.kind,
        'file_size': instance.size_bytes,
        'gdpr_relevant': True
    }
    
    if context.get('is_family_access'):
        # СЕМЬЯ одобрила через веб-интерфейс
        actor_type, actor_id = _get_actor_info()
        metadata['access_type'] = 'family_web'
        
    elif context.get('is_family_invite'):
        # Семья получила приглашение
        actor_type, actor_id = _get_actor_info()
        metadata['access_type'] = 'family_invite'
        
        family_token = get_family_token()
        if family_token:
            safe_token = family_token[:8] + '...' if len(family_token) > 8 else '***'
            metadata['token_preview'] = safe_token
        
    elif context.get('is_partner_access'):
        actor_type, actor_id = _get_actor_info()
    
    AuditLog.objects.create(
        actor_type=actor_type,
        actor_id=actor_id,
        action='upload_media',
        target_type='media',
        target_id=instance.id,
        metadata=metadata
    )