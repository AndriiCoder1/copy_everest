from django.db import models

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
        indexes = [
            models.Index(fields=['memorial','created_at']),
        ]

class MediaThumbnail(models.Model):
    asset = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name='thumbnails')
    preset = models.CharField(max_length=16)
    file = models.FileField(upload_to='thumbnails/')
    size_bytes = models.IntegerField()

    class Meta:
        unique_together = [('asset','preset')]
