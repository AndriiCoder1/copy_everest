from django.db import models
from django.conf import settings

class Tribute(models.Model):
    memorial = models.ForeignKey(
        'memorials.Memorial', 
        on_delete=models.CASCADE, 
        related_name='tributes'
    )
    author_name = models.CharField(max_length=120)
    author_email = models.EmailField(null=True, blank=True)  # ← Добавить blank=True
    text = models.TextField()
    status = models.CharField(
        max_length=10, 
        choices=[
            ('pending', 'For moderation'),    # ← Улучшить названия для админки
            ('approved', 'Approved'),
            ('rejected', 'Rejected')
        ], 
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)  # ← Добавить blank=True
    moderated_by_user = models.ForeignKey(
        'partners.PartnerUser', 
        null=True, 
        blank=True,                         # ← КРИТИЧНО: добавить blank=True
        on_delete=models.SET_NULL,
        editable=False,                     # ← Важно: скрыть из форм
        verbose_name='partner moderator' 
    )
    updated_at = models.DateTimeField(auto_now=True)  # ← Добавить для отслеживания изменений

    class Meta:
        indexes = [models.Index(fields=['memorial', 'status', 'created_at'])]
        verbose_name = 'Tribute'      # ← Для красивого отображения в админке
        verbose_name_plural = 'Tributes'
        ordering = ['-created_at']           # ← Сортировка по умолчанию
    
    def __str__(self):
        return f"Tribute from {self.author_name} ({self.status})" 
    
    def save(self, *args, **kwargs):
        # Автоматически обновляем approved_at при одобрении
        if self.status == 'approved' and not self.approved_at:
            from django.utils import timezone
            self.approved_at = timezone.now()
        elif self.status != 'approved':
            self.approved_at = None
        
        super().save(*args, **kwargs)