import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings 
from django.utils import timezone
from .models import Tribute
from .tasks import moderate_tribute_with_ai
from django.db import transaction

logger = logging.getLogger(__name__)

# Сигнал для отправки уведомления о новом трибиту
@receiver(post_save, sender=Tribute)
def send_tribute_notification(sender, instance, created, **kwargs):
    """Sends notification to family about new tribute""" 
    if created and instance.status == 'pending':
        #print(f"=== SIGNAL: New tribute {instance.id} for memorial {instance.memorial.short_code}")
        
        memorial = instance.memorial
        
        # Используем правильное имя связи: invites (как указано в related_name)
        invites = memorial.invites.filter(
            consumed_at__isnull=True,          
            expires_at__gt=timezone.now()      
        )
        
        #print(f"DEBUG: Found {invites.count()} active invites for memorial {memorial.short_code}")
        
        if invites.count() == 0:
            #print(f"WARNING: No active invites found for memorial {memorial.short_code}")
            #print(f"  Memorial: {memorial.short_code}, Status: {memorial.status}")
            return       
        for invite in invites:
            subject = f'New tribute for memorial {memorial.first_name} {memorial.last_name}' 
            message = f'''
New tribute for memorial {memorial.first_name} {memorial.last_name}.

Author: {instance.author_name}
Message: {instance.text[:200]}...

To moderate, go to:
http://172.20.10.4:8000/memorials/{memorial.short_code}/moderate/?token={invite.token}
'''
            
            #try:
                # Для тестирования выводим в консоль
                #print(f"EMAIL NOTIFICATION would be sent to: {invite.email}")
                #print(f"Subject: {subject}")
                #print(f"Message: {message[:100]}...")
                #print("-" * 50)
                
                # Раскомментируйте для реальной отправки, когда настроите SMTP:
                # send_mail(
                #     subject=subject,
                #     message=message,
                #     from_email=settings.DEFAULT_FROM_EMAIL,
                #     recipient_list=[invite.email],
                #     fail_silently=True
                # )
                
            #except Exception as e:
                #print(f"ERROR sending email: {e}")
                #pass

def safe_send_to_celery(tribute_id):
    """Безопасная отправка задачи в Celery"""
    try:
        moderate_tribute_with_ai.delay(tribute_id)
        logger.info(f"Задача отправлена в Celery для трибьюта {tribute_id}")
    except Exception as e:
        logger.error(f"Celery недоступен, запускаем синхронно: {e}")
        # Запускаем задачу синхронно
        #try:
            #from tributes.utils import moderate_tribute_sync
            #result = moderate_tribute_sync(tribute_id)
            #logger.info(f"Синхронный результат: {result}")
        #except Exception as sync_error:
            #logger.error(f"Ошибка синхронного запуска: {sync_error}")                

@receiver(post_save, sender=Tribute)
def auto_trigger_ai_moderation(sender, instance, created, **kwargs):
    """
    Автоматически запускает ИИ-модерацию для новых трибьютов со статусом 'pending'
    """
    try:
        # Только для новых записей или если статус изменился на pending
        if not created and not instance.tracker.has_changed('status'):
            return
            
        # Проверяем настройки авто-модерации
        ai_settings = getattr(settings, 'AI_MODERATION_SETTINGS', {})
        
        if not ai_settings.get('auto_moderate_new', True):
            return
            
        # Только для pending и если ещё не модерировалось ИИ
        if instance.status == 'pending' and not instance.ai_moderated_at:
            logger.info(f"Auto-triggering AI moderation for tribute {instance.id}")
            
            # Запускаем задачу в Celery после успешного коммита транзакции
            transaction.on_commit(
                lambda: safe_send_to_celery(instance.id)
            )
    except Exception as e:
        logger.error(f"Error in auto_trigger_ai_moderation: {e}")               