from django.db import models
from model_utils import FieldTracker
from django.utils.translation import gettext_lazy as _
import secrets
from django.utils import timezone
from django.conf import settings

# ===== МОДЕЛЬ МЕМОРИАЛА =====
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tracker = FieldTracker()
    language = models.CharField(
        max_length=2, 
        default='de',
        choices=[('de', 'Deutsch'), ('fr', 'Français'), ('it', 'Italiano'), ('en', 'English')]
    )
    
    def save(self, *args, **kwargs):
        # Сохраняем измененные поля перед сохранением
        self._changed_fields = self.tracker.changed()
        super().save(*args, **kwargs)

    def __str__(self):
       # Показываем фамилию, имя, код И название фирмы партнёра
       partner_name = self.partner.name if self.partner else "Without a partner" 
       return f"{self.last_name} {self.first_name} ({self.short_code}) - {partner_name}"

    class Meta:
        verbose_name = _('Memorial')
        verbose_name_plural = _('Memorials')
        constraints = [
            models.CheckConstraint(check=models.Q(storage_bytes_used__lte=models.F('storage_bytes_limit')), name='storage_limit_check'),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['partner','created_at']),
        ]
# ===== МОДЕЛЬ ПРИГЛАШЕНИЯ ДЛЯ СЕМЬИ =====
class FamilyInvite(models.Model):
    memorial = models.ForeignKey(Memorial, on_delete=models.CASCADE, related_name='invites')
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)

    class Meta:
        verbose_name = _('Family Invite')
        verbose_name_plural = _('Family Invites')
        indexes = [models.Index(fields=['memorial','expires_at'])]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # Автогенерация токена при создании
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        
        # Устанавливаем expires_at, если не установлен
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=90)
        
        super().save(*args, **kwargs)
        
    def get_family_url(self):
        """Returns family URL only if requested by the admin (for viewing)"""
        # Can show only truncated version
        return f"/memorials/{self.memorial.short_code}/family/?token=••••••••"


class LanguageOverride(models.Model):
    memorial = models.ForeignKey(Memorial, on_delete=models.CASCADE, related_name='language_overrides')
    language_code = models.CharField(max_length=5)  
    field_name = models.CharField(max_length=100)  
    translated_text = models.TextField()           
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('memorial', 'language_code', 'field_name')]
        verbose_name = _('Language Override')
        verbose_name_plural = _('Language Overrides')

    def __str__(self):
        # Показываем язык, поле и связанный мемориал
        memorial_info = f"Memorial #{self.memorial.id}"
        if hasattr(self.memorial, 'short_code'):
            memorial_info = self.memorial.short_code
        return f"{self.language_code}:{self.field_name} for {memorial_info}"    

class QRCode(models.Model):
    memorial = models.ForeignKey(Memorial, on_delete=models.CASCADE, related_name='qrcodes')
    version = models.IntegerField(default=1)
    qr_png = models.FileField(upload_to='qr/', null=True)
    qr_pdf = models.FileField(upload_to='qr/', null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('QR Code')
        verbose_name_plural = _('QR Codes')
        indexes = [models.Index(fields=['memorial','created_at'])]
    
    def __str__(self):
        # Показываем версию и связанный мемориал
        memorial_info = f"Memorial #{self.memorial.id}"
        if hasattr(self.memorial, 'short_code'):
            memorial_info = self.memorial.short_code
        return f"QR Code v{self.version} for {memorial_info}"