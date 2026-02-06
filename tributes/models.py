from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker
from django.utils import timezone

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
        
        # Сохраняем результат ИИ
        self.ai_moderation_result = ai_result
        self.ai_moderated_at = timezone.now()
        self.ai_confidence = confidence
        self.ai_verdict = verdict
        
        action_taken = None
        auto_action = False
        
        # Автоматические действия на основе высокой уверенности ИИ
        # (можно настроить пороги в настройках)
        if confidence >= 0.85:
            if verdict == 'approved_ai' and self.status == 'pending':
                self.status = 'approved'
                self.approved_at = timezone.now()
                action_taken = 'ai_auto_approve'
                auto_action = True
            elif verdict == 'rejected_ai' and self.status == 'pending':
                self.status = 'rejected'
                action_taken = 'ai_auto_reject'
                auto_action = True
        else:
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
            actor_id=None,  # У ИИ нет ID пользователя
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
                'auto_action_taken': auto_action,
                'gdpr_relevant': True,
                'final_status': self.status,
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
                # Если tasks.py еще не создан, пока пропускаем
                # Позже можно добавить fallback-логику
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