from django.db import models

class ShortLink(models.Model):
    memorial = models.ForeignKey('memorials.Memorial', on_delete=models.CASCADE, related_name='shortlinks')
    code = models.CharField(max_length=16, unique=True)
    target_url = models.TextField()
    visits_count = models.BigIntegerField(default=0)
    last_visited_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=['code'])]
