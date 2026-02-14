import os
from django.utils.timezone import now
from django.db import models
from django.utils.translation import gettext_lazy as _

def get_asset_upload_path(instance, filename):
    """
    Генерирует путь для загрузки файла в формате:
    assets/memorials/<memorial_id>/<kind>/<год>/<месяц>/<день>/<filename>
    """
    # Получаем расширение файла
    ext = filename.split('.')[-1] if '.' in filename else ''
    base_name = os.path.splitext(filename)[0]
    
    # Создаем уникальное имя с timestamp
    timestamp = now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{base_name}_{timestamp}.{ext}" if ext else f"{base_name}_{timestamp}"
    
    # Формируем путь: assets/memorials/11/images/2026/02/14/photo_20260214_123456.jpg
    path = os.path.join(
        'assets',
        'memorials',
        str(instance.memorial_id),
        instance.kind.lower(),
        now().strftime('%Y/%m/%d'),
        unique_filename
    )
    return path

# Модель для хранения медиафайлов (фотографий, видео)
class MediaAsset(models.Model):
    memorial = models.ForeignKey('memorials.Memorial', on_delete=models.CASCADE, related_name='assets')
    kind = models.CharField(max_length=16)
    file = models.FileField(upload_to=get_asset_upload_path)
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

    def save(self, *args, **kwargs):
        # Автоматически заполняем original_filename при сохранении
        if not self.original_filename and self.file:
            self.original_filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)
        
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
