from django.db import models
from django.utils.translation import gettext_lazy as _

# Модель для хранения медиафайлов (фотографий, видео)
class MediaAsset(models.Model):
    memorial = models.ForeignKey('memorials.Memorial', on_delete=models.CASCADE, related_name='assets')
    kind = models.CharField(max_length=16)
    file = models.FileField(upload_to='assets/')
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.BigIntegerField(blank=True, null=True)
    width = models.IntegerField(blank=True, null=True)
    height = models.IntegerField(blank=True, null=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True, null=True, unique=False)
    uploaded_by_user = models.ForeignKey('partners.PartnerUser', null=True, on_delete=models.SET_NULL)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Media Asset')
        verbose_name_plural = _('Media Assets')
        indexes = [
            models.Index(fields=['memorial','created_at']),
        ]
    def __str__(self):
        return f"{self.original_filename or self.file.name}"

# Модель для хранения миниатюр медиафайлов
class MediaThumbnail(models.Model):
    asset = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name='thumbnails')
    preset = models.CharField(max_length=16)
    file = models.FileField(upload_to='thumbnails/')
    size_bytes = models.IntegerField()

    class Meta:
        verbose_name = _('Media Thumbnail')
        verbose_name_plural = _('Media Thumbnails')
        unique_together = [('asset','preset')]

    def __str__(self):
        return f"Thumbnail for {self.asset}"
