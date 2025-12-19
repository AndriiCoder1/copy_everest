from django.db import models

class Partner(models.Model):
    name = models.CharField(max_length=160)
    legal_name = models.CharField(max_length=160)
    billing_email = models.EmailField(unique=True)
    locale = models.CharField(max_length=8, default='de-ch')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

    class Meta:
        indexes = [models.Index(fields=['created_at'])]

class PartnerUser(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='users')
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=[('admin','admin'),('staff','staff')])
    created_at = models.DateTimeField(auto_now_add=True)
    #user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='partner_user')
    class Meta:
        indexes = [models.Index(fields=['partner', 'role'])]
