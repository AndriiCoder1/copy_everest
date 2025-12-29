from django.db import models
from partners.models import PartnerUser  # Импортируем здесь
from django.contrib.auth.models import User  # Импортируем здесь

class AuditLog(models.Model):
    actor_type = models.CharField(max_length=24)
    actor_id = models.BigIntegerField()
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=24)
    target_id = models.BigIntegerField()
    metadata = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def get_actor_display(self):
        """Возвращает читаемое представление актора для админки."""
        try:
            if self.actor_type == 'partner_user':
                pu = PartnerUser.objects.get(id=self.actor_id)
                return f"{pu.email} (PartnerUser ID: {self.actor_id})"
            elif self.actor_type == 'admin' or self.actor_type == 'user':
                u = User.objects.get(id=self.actor_id)
                return f"{u.username} (User ID: {self.actor_id})"
            elif self.actor_type == 'family':
                return f"Family Member (via token)"
        except (PartnerUser.DoesNotExist, User.DoesNotExist):
            pass
        return f"{self.actor_type} (ID: {self.actor_id})"

    def __str__(self):
        # Обновляем, чтобы использовался новый метод
        return f"{self.action} by {self.get_actor_display()} on {self.target_type}#{self.target_id}"