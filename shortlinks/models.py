from django.db import models
from django.utils.translation import gettext_lazy as _

class ShortLink(models.Model):
    memorial = models.ForeignKey('memorials.Memorial', on_delete=models.CASCADE, related_name='shortlinks')
    code = models.CharField(max_length=16, unique=True)
    target_url = models.TextField()
    visits_count = models.BigIntegerField(default=0)
    last_visited_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.code} -> {self.target_url}"
    
    class Meta:
        verbose_name = _('Short Link')
        verbose_name_plural = _('Short Links')
        indexes = [models.Index(fields=['code'])]


