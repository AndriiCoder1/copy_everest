from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import AuditLog
from memorials.models import Memorial
from tributes.models import Tribute
from assets.models import MediaAsset
from .middleware import get_current_user

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

@receiver(post_save, sender=Memorial)
def log_memorial_change(sender, instance, created, **kwargs):
    action = 'create' if created else 'update'
    
    # Логируем только важные поля для GDPR
    gdpr_fields_changed = False
    if not created and hasattr(instance, '_changed_fields'):
        # Проверяем, изменились ли персональные данные
        sensitive_fields = ['first_name', 'last_name', 'biography', 'date_of_birth', 'date_of_death']
        if any(field in instance._changed_fields for field in sensitive_fields):
            gdpr_fields_changed = True
    
    if created or gdpr_fields_changed:
        # Определяем actor (кто изменил)
        actor_type, actor_id = _get_actor_info()
     
        
        # Здесь нужно определить, кто совершил действие (через request или контекст)
        # Можно использовать threading.local или middleware
        
        AuditLog.objects.create(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type='memorial',
            target_id=instance.id,
            metadata={
                'memorial_id': instance.id,
                'short_code': instance.short_code,
                'changed_fields': instance._changed_fields if hasattr(instance, '_changed_fields') else None,
                'gdpr_relevant': True
            }
        )

# Логирование создания и модерации тributes
@receiver(post_save, sender=Tribute)
def log_tribute_approval(sender, instance, created, **kwargs):
    print(f"=== AUDIT DEBUG: Tribute post_save signal fired. Created: {created}, ID: {instance.id}, Sender: {sender} ===")
    actor_type, actor_id = _get_actor_info()
    
    # 1. ЛОГИРОВАНИЕ СОЗДАНИЯ НОВОГО ТРИБУТА
    if created:
        AuditLog.objects.create(
            actor_type=actor_type,
            actor_id=actor_id,
            action='create_tribute',
            target_type='tribute',
            target_id=instance.id,
            metadata={
                'memorial_id': instance.memorial.id,
                'memorial_code': instance.memorial.short_code,
                'author_name': instance.author_name,
                'initial_status': 'awaiting_moderation',  
                'gdpr_relevant': True  
            }
        )
        return  
    
    # 2. ЛОГИРОВАНИЕ МОДЕРАЦИИ (одобрение/отклонение) 
    if instance.tracker.has_changed('is_approved'):
        # Если актор - system (не аутентифицирован), возможно, это семья через токен
        if actor_type == 'system' and hasattr(instance, 'moderated_by_family'):
            actor_type = 'family'
        
        AuditLog.objects.create(
            actor_type=actor_type,
            actor_id=actor_id,
            action='moderate_tribute',
            target_type='tribute',
            target_id=instance.id,
            metadata={
                'memorial_id': instance.memorial.id,
                'old_status': instance.tracker.previous('is_approved'),
                'new_status': instance.is_approved,
                'gdpr_relevant': True
            }
        )

@receiver(post_save, sender=MediaAsset)
def log_media_access(sender, instance, created, **kwargs):
    print(f"=== DEBUG: MediaAsset post_save signal fired. Created: {created}, ID: {instance.id} ===")
    print(f"=== DEBUG: Memorial ID from instance: {instance.memorial.id} ===")

    if created:
        # 1. ПОЛУЧАЕМ АКТОРА
        actor_type, actor_id = _get_actor_info()
        print(f"=== DEBUG: Actor determined. Type: {actor_type}, ID: {actor_id} ===")

        # 2. ПОДГОТАВЛИВАЕМ МЕТАДАННЫЕ
        metadata = {
            'memorial_id': instance.memorial.id,
            'file_type': instance.kind,
            'file_size': instance.size_bytes,
            'gdpr_relevant': True
        }
        print(f"=== DEBUG: Metadata prepared: {metadata} ===")

        # 3. ПЫТАЕМСЯ СОЗДАТЬ ЗАПИСЬ С ОБРАБОТКОЙ ОШИБОК
        try:
            log_entry = AuditLog.objects.create(
                actor_type=actor_type,
                actor_id=actor_id,
                action='upload_media',
                target_type='media',
                target_id=instance.id,
                metadata=metadata
            )
            print(f"✅ SUCCESS: AuditLog record created with ID: {log_entry.id}")
        except Exception as e:
            # Эта строка покажет, что именно пошло не так
            print(f"❌ ERROR: Failed to create AuditLog. Exception: {e}")
            import traceback
            traceback.print_exc() 