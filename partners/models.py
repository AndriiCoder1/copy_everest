from django.db import models
from django.utils.translation import gettext_lazy as _

class Partner(models.Model):
    name = models.CharField(max_length=160)
    legal_name = models.CharField(max_length=160)
    billing_email = models.EmailField(unique=True)
    locale = models.CharField(max_length=8, default='de-ch')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Partner')
        verbose_name_plural = _('Partners')
        indexes = [models.Index(fields=['created_at'])]
        
    def __str__(self):
        return self.name


class PartnerUser(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='users')
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=[('admin','admin'),('staff','staff')])
    created_at = models.DateTimeField(auto_now_add=True)
    #user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='partner_user')
    class Meta:
        verbose_name = _('Partner User')
        verbose_name_plural = _('Partner Users')
        indexes = [models.Index(fields=['partner', 'role'])]
    
    def __str__(self):
        return f"{self.email} ({self.role})"