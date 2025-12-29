import os
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.files.base import ContentFile
from django.conf import settings
import qrcode
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from .models import Memorial, QRCode
from django.db.models import Max
from datetime import datetime

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Memorial)
def generate_qr_on_activation(sender, instance, created, **kwargs):
    """
    Автоматически генерирует QR-коды при активации мемориала
    """
    if instance.status == 'active':
        # Проверяем, есть ли уже QR-код
        if not QRCode.objects.filter(memorial=instance).exists():
            try:
                memorial_url = f"http://172.20.10.4:8000/memorials/{instance.short_code}/public/"
                
                # Генерация PNG
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(memorial_url)
                qr.make(fit=True)
                
                qr_img = qr.make_image(fill_color="black", back_color="white")
                img_buffer = io.BytesIO()
                qr_img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                # Генерация PDF
                pdf_buffer = io.BytesIO()
                c = canvas.Canvas(pdf_buffer, pagesize=A4)
                img_reader = ImageReader(img_buffer)
                c.drawImage(img_reader, 100, 500, width=200, height=200, preserveAspectRatio=True)
                
                # Текст в PDF
                c.setFont("Helvetica-Bold", 16) 
                c.drawString(100, 450, "EverEst - Digital Memory")
                c.setFont("Helvetica", 14)
                c.drawString(100, 425, f"In Memory of {instance.first_name} {instance.last_name}")
                c.setFont("Helvetica", 12)
                c.drawString(100, 400, f"Memorial Code: {instance.short_code}")
                c.drawString(100, 380, f"Created: {instance.created_at.strftime('%Y-%m-%d')}")
                c.drawString(100, 360, "Scan QR code to visit memorial page")
                c.showPage()
                c.save()
                pdf_buffer.seek(0)
                
                # Создание записи QRCode
                max_version = QRCode.objects.filter(
                    memorial=instance
                ).aggregate(Max('version'))['version__max'] or 0
                
                qr_code = QRCode.objects.create(
                    memorial=instance,
                    version=max_version + 1
                )
                
                # Сохранение файлов
                qr_code.qr_png.save(
                    f"qr_{instance.short_code}_v{qr_code.version}.png",
                    ContentFile(img_buffer.getvalue())
                )
                qr_code.qr_pdf.save(
                    f"qr_{instance.short_code}_v{qr_code.version}.pdf",
                    ContentFile(pdf_buffer.getvalue())
                )
                
                logger.info(f"QR-код создан для мемориала {instance.short_code}")
                
            except Exception as e:
                logger.error(f"Ошибка генерации QR для {instance.short_code}: {e}")