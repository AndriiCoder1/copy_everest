from django.db import models

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
