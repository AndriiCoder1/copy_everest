from django.db import models
from partners.models import PartnerUser 
from django.contrib.auth.models import User 
from django.utils.translation import gettext_lazy as _

# Модель для хранения аудита действий пользователей
class AuditLog(models.Model):
    ACTOR_TYPES = [
        ('system', 'System'),
        ('superuser', 'Superuser'),
        ('partner_user', 'Partner User'),
        ('family', 'Family'),
        ('guest', 'Guest'),
    ]
    actor_type = models.CharField(max_length=24, choices=ACTOR_TYPES)
    actor_id = models.BigIntegerField(null=True, blank=True) 
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=24)
    target_id = models.BigIntegerField()
    metadata = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['actor_type', 'actor_id']),
        ]
    # Метод для отображения актора в админке
    def get_actor_display(self):
        if self.actor_type == 'family':
            token = self.metadata.get('token_preview', 'unknown')
            email = self.metadata.get('family_email', '')
            return f"Family ({email}) [{token}]" if email else f"Family [{token}]"

        elif self.actor_type == 'guest':
            return "Guest"

        elif self.actor_type == 'user' and self.actor_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=self.actor_id)
                return f"{user.email}"  # Просто email, без ID
            except User.DoesNotExist:
                return f"User ID: {self.actor_id}"  

        elif self.actor_type == 'partner_user' and self.actor_id:
            try:
                pu = PartnerUser.objects.get(id=self.actor_id)
                return f"{pu.email} (Partner)"
            except PartnerUser.DoesNotExist:
                return f"PartnerUser ID: {self.actor_id}"

        elif self.actor_type == 'system':
            return "System"

        elif self.actor_type == 'superuser':
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=self.actor_id)
                return f"{user.email} (Superuser)"
            except User.DoesNotExist:
                return f"Superuser ID: {self.actor_id}"

        elif self.actor_id:
            return f"{self.actor_type} ID: {self.actor_id}"

        return self.actor_type

    def __str__(self):
        return f"{self.action} by {self.get_actor_display()} on {self.target_type}#{self.target_id}"