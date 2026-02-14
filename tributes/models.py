from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class Tribute(models.Model):
    memorial = models.ForeignKey(
        'memorials.Memorial', 
        on_delete=models.CASCADE, 
        related_name='tributes'
    )
    author_name = models.CharField(max_length=120)
    author_email = models.EmailField(null=True, blank=True)  
    text = models.TextField()
    status = models.CharField(
        max_length=10, 
        choices=[
            ('pending', _('For moderation')),
            ('approved', _('Approved')),
            ('rejected', _('Rejected'))
        ], 
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)  
    moderated_by_user = models.ForeignKey(
        'partners.PartnerUser', 
        null=True, 
        blank=True,                         
        on_delete=models.SET_NULL,
        editable=False,                     
        verbose_name=_('partner moderator') 
    )
    updated_at = models.DateTimeField(auto_now=True)


    # === ПОЛЯ ИИ-МОДЕРАЦИИ ===
    ai_moderation_result = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('AI Moderation Result'),
        help_text=_('JSON with AI analysis and verdict')
    )
    ai_moderated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('AI Moderation Time')
    )
    ai_confidence = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('AI Confidence'),
        help_text=_('Confidence score from 0.0 to 1.0')
    )
    ai_verdict = models.CharField(
        max_length=20,
        choices=[
            ('pending_ai', _('Pending AI Review')),
            ('approved_ai', _('AI Approved')),
            ('rejected_ai', _('AI Rejected')),
            ('flag_ai', _('AI Flagged for Review')),
            ('error_ai', _('AI Error'))
        ],
        default='pending_ai',
        verbose_name=_('AI Verdict')
    )

    tracker = FieldTracker()  

    class Meta:
        verbose_name = _('Tribute')     
        verbose_name_plural = _('Tributes')
        indexes = [
            models.Index(fields=['memorial', 'status', 'created_at']),
            # Индексы для быстрого поиска по ИИ-полям
            models.Index(fields=['ai_verdict', 'created_at']),
            models.Index(fields=['status', 'ai_verdict']),
        ]
        ordering = ['-created_at']          
    
    def __str__(self):
        return f"Tribute from {self.author_name or 'Anonymous'} ({self.status})"
    
    def save(self, *args, **kwargs):

        self._changed_fields = self.tracker.changed()
        # Автоматически обновляем approved_at при одобрении
        if self.status == 'approved' and not self.approved_at:
            self.approved_at = timezone.now()
        elif self.status != 'approved':
            self.approved_at = None
        
        super().save(*args, **kwargs)

   
    # === МЕТОДЫ ДЛЯ ИИ-МОДЕРАЦИИ ===
    def apply_ai_verdict(self, ai_result):
        """
        Применяет вердикт ИИ к трибьюту и логирует действие.
        """
        from audits.models import AuditLog  
    
        verdict = ai_result.get('verdict', 'flag_ai')
        confidence = ai_result.get('confidence', 0.5)
        reasoning = ai_result.get('reasoning', '')
        flags = ai_result.get('flags', [])
        name_context = ai_result.get('name_context', 'unknown')
    
        # Получаем пороги из настроек
        thresholds = settings.AI_MODERATION_SETTINGS.get('confidence_thresholds', {})
        auto_approve = thresholds.get('auto_approve', 0.8)
        auto_reject = thresholds.get('auto_reject', 0.7)

        # Настройки проверки имён
        name_strictness = settings.AI_MODERATION_SETTINGS.get('name_verification_strictness', 'strict')
        name_check = settings.AI_MODERATION_SETTINGS.get('name_check', {})
        
        logger.info(f"Applying AI verdict for tribute {self.id}: verdict={verdict}, confidence={confidence}")
        logger.info(f"Thresholds: approve={auto_approve}, reject={auto_reject}")
        logger.info(f"Name context: {name_context}, Flags: {flags}")

        # Сохраняем результат ИИ
        self.ai_moderation_result = ai_result
        self.ai_moderated_at = timezone.now()
        self.ai_confidence = confidence
        self.ai_verdict = verdict
        
        action_taken = None
        auto_action = False
        
        # 1. Сначала проверяем КРИТИЧЕСКИЕ ошибки имён
        critical_name_errors = ['wrong_both_names', 'wrong_first_name', 'wrong_last_name']
        has_critical_name_error = any(error in str(flags) for error in critical_name_errors)
    
        if has_critical_name_error:
            # Критическая ошибка имени - НЕ одобряем даже с высоким confidence!
            self.status = 'pending'  # На ручную проверку
            action_taken = 'ai_flag_name_mismatch'
            auto_action = False
            logger.warning(f"Critical name error for tribute {self.id}: {name_context}")

        # 2. Затем проверяем REJECT (самый высокий приоритет после критических ошибок)
        elif confidence >= auto_reject and verdict == 'rejected_ai':
            self.status = 'rejected'
            action_taken = 'ai_auto_reject'
            auto_action = True
            logger.info(f"Auto-rejected tribute {self.id}")    
    
        # 3. Потом APPROVE
        elif confidence >= auto_approve and verdict == 'approved_ai':
            # Проверяем предупреждения об именах
            name_warnings = ['different_name_mentioned', 'partial_name_first_only', 'partial_name_last_only']
            has_name_warning = any(warning in str(flags) for warning in name_warnings)

            if has_name_warning and name_strictness == 'strict':
                self.status = 'pending'
                action_taken = 'ai_flag_name_warning'
                auto_action = False
                logger.info(f"Name warning in strict mode: tribute {self.id} flagged")
            else:
                self.status = 'approved'
                self.approved_at = timezone.now()
                action_taken = 'ai_auto_approve'
                auto_action = True
                logger.info(f"Auto-approved tribute {self.id}")
            
        else:
            action_taken = 'ai_flag_review'
            logger.info(f"Tribute {self.id} needs manual review (confidence={confidence})")
    
        # Если не было авто-действия и статус не изменился
        if not action_taken and self.status == 'pending':
            action_taken = 'ai_flag_review'
            
    
        # Сохраняем изменения
        self.save(update_fields=[
            'ai_moderation_result',
            'ai_moderated_at', 
            'ai_confidence',
            'ai_verdict',
            'status',
            'approved_at'
        ])
    
        # Логируем действие ИИ
        AuditLog.objects.create(
            actor_type='ai_moderator',
            actor_id=None,
            action=action_taken or 'ai_moderation_complete',
            target_type='tribute',
            target_id=self.id,
            metadata={
                'tribute_id': self.id,
                'memorial_id': self.memorial.id,
                'ai_verdict': verdict,
                'ai_confidence': confidence,
                'ai_reasoning': reasoning,
                'ai_flags': flags,
                'name_context': name_context,
                'auto_action_taken': auto_action,
                'gdpr_relevant': True,
                'final_status': self.status,
                'thresholds_used': { 
                'auto_approve': auto_approve,
                'auto_reject': auto_reject
                }
            }
        )
    
        return {
            'action': action_taken,
            'auto_action': auto_action,
            'verdict': verdict,
            'confidence': confidence
        }
    
    def trigger_ai_moderation(self):
        """
        Триггерит асинхронную ИИ-модерацию для этого трибьюта.
        """
        from django.core.cache import cache
        
        # Используем кэш как блокировку, чтобы не запускать повторно
        lock_key = f'tribute_ai_lock_{self.id}'
        
        # Запускаем только если:
        # 1. Трибьют в статусе pending
        # 2. ИИ еще не модерировал
        # 3. Нет активной блокировки
        if (self.status == 'pending' and 
            not self.ai_moderated_at and 
            not cache.get(lock_key)):
            
            # Устанавливаем блокировку на 5 минут
            cache.set(lock_key, True, timeout=300)
            
            # Импортируем и запускаем задачу
            try:
                from .tasks import moderate_tribute_with_ai
                moderate_tribute_with_ai.delay(self.id)
                return True
            except ImportError:
                cache.delete(lock_key)
                return False
        
        return False
    
    def get_ai_moderation_display(self):
        """
        Возвращает читаемое представление результата AI-модерации.
        """
        if not self.ai_moderation_result:
            return _("No AI moderation yet")
        
        result = self.ai_moderation_result
        verdict_display = dict(self._meta.get_field('ai_verdict').choices).get(
            self.ai_verdict, 
            self.ai_verdict
        )
        
        return {
            'verdict': verdict_display,
            'confidence': f"{self.ai_confidence:.0%}" if self.ai_confidence else "N/A",
            'reasoning': result.get('reasoning', ''),
            'time': self.ai_moderated_at.strftime("%Y-%m-%d %H:%M") if self.ai_moderated_at else None,
            'flags': result.get('flags', [])
        }    