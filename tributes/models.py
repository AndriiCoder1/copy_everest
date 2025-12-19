from django.db import models

class Tribute(models.Model):
    memorial = models.ForeignKey('memorials.Memorial', on_delete=models.CASCADE, related_name='tributes')
    author_name = models.CharField(max_length=120)
    author_email = models.EmailField(null=True)
    text = models.TextField()
    status = models.CharField(max_length=10, choices=[('pending','pending'),('approved','approved'),('rejected','rejected')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True)
    moderated_by_user = models.ForeignKey('partners.PartnerUser', null=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [models.Index(fields=['memorial','status','created_at'])]
