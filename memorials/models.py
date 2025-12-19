from django.db import models

class Memorial(models.Model):
    partner = models.ForeignKey('partners.Partner', on_delete=models.CASCADE, related_name='memorials')
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    birth_date = models.DateField(null=True)
    death_date = models.DateField(null=True)
    quote = models.CharField(max_length=300, blank=True)
    biography_language = models.CharField(max_length=5, default='en')
    status = models.CharField(max_length=16, choices=[('draft','draft'),('active','active')], default='draft')
    slug = models.SlugField(max_length=64, unique=True)
    short_code = models.CharField(max_length=16, unique=True)
    family_contact_email = models.EmailField()
    theme_key = models.CharField(max_length=32, default='calm')
    storage_bytes_used = models.BigIntegerField(default=0)
    storage_bytes_limit = models.BigIntegerField(default=1073741824)
    subscription_start_at = models.DateTimeField(null=True)
    subscription_end_at = models.DateTimeField(null=True)
    qr_png = models.FileField(upload_to='qr/', null=True, blank=True) # QR код в формате PNG поменял добавил blank=True
    qr_pdf = models.FileField(upload_to='qr/', null=True, blank=True) # QR код в формате PDF поменял добавил blank=True
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
    # Показываем фамилию, имя, код И название фирмы партнёра
       partner_name = self.partner.name if self.partner else "Без партнёра"
       return f"{self.last_name} {self.first_name} ({self.short_code}) - {partner_name}"

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(storage_bytes_used__lte=models.F('storage_bytes_limit')), name='storage_limit_check'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['partner','created_at']),
        ]

class FamilyInvite(models.Model):
    memorial = models.ForeignKey(Memorial, on_delete=models.CASCADE, related_name='invites')
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=['memorial','expires_at'])]

class LanguageOverride(models.Model):
    memorial = models.ForeignKey(Memorial, on_delete=models.CASCADE, related_name='language_overrides')
    language_code = models.CharField(max_length=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('memorial','language_code')]

class QRCode(models.Model):
    memorial = models.ForeignKey(Memorial, on_delete=models.CASCADE, related_name='qrcodes')
    version = models.IntegerField(default=1)
    qr_png = models.FileField(upload_to='qr/', null=True)
    qr_pdf = models.FileField(upload_to='qr/', null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['memorial','created_at'])]
