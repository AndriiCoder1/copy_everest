from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from model_utils import FieldTracker

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

    tracker = FieldTracker()  

    class Meta:
        verbose_name = _('Tribute')     
        verbose_name_plural = _('Tributes')
        indexes = [models.Index(fields=['memorial', 'status', 'created_at'])]
        ordering = ['-created_at']          
    
    def __str__(self):
        return f"Tribute from {self.author_name or 'Anonymous'} ({self.status})"
    
    def save(self, *args, **kwargs):

        self._changed_fields = self.tracker.changed()
        # Автоматически обновляем approved_at при одобрении
        if self.status == 'approved' and not self.approved_at:
            from django.utils import timezone
            self.approved_at = timezone.now()
        elif self.status != 'approved':
            self.approved_at = None
        
        super().save(*args, **kwargs)