from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F
from django.core.files.storage import default_storage
import hashlib

from everest.permissions import IsPartnerOrFamily, get_partner_user
from memorials.models import Memorial
from .models import MediaAsset

ALLOWED_MIME = {'image/jpeg','image/png','image/webp','application/pdf'}

class MediaUpload(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsPartnerOrFamily]
    
    def post(self, request, memorial_id):
        # Получаем мемориал с проверкой прав
        memorial = self._get_memorial_with_permission_check(request, memorial_id)
        if isinstance(memorial, Response):
            return memorial
        
        file = request.data.get('file')
        if not file:
            return Response({'detail':'file required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if file.content_type not in ALLOWED_MIME:
            return Response({'detail':'unsupported type'}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        
        size = file.size
        with transaction.atomic():
            memorial.refresh_from_db()
            if memorial.storage_bytes_used + size > memorial.storage_bytes_limit:
                return Response({'detail':'storage limit exceeded'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
            
            checksum = hashlib.sha256(file.read()).hexdigest()
            file.seek(0)
            
            if MediaAsset.objects.filter(checksum_sha256=checksum).exists():
                return Response({'detail':'duplicate'}, status=status.HTTP_409_CONFLICT)
            
            asset = MediaAsset.objects.create(
                memorial=memorial,
                kind='image' if file.content_type.startswith('image/') else 'document',
                file=file,
                original_filename=file.name,
                mime_type=file.content_type,
                size_bytes=size,
                checksum_sha256=checksum,
            )
            Memorial.objects.filter(pk=memorial.pk).update(storage_bytes_used=F('storage_bytes_used') + size)
        
        return Response({'id': asset.id}, status=status.HTTP_201_CREATED)
    
    def _get_memorial_with_permission_check(self, request, memorial_id):
        """Проверяет права на доступ к мемориалу"""
        # Для партнера
        partner_user = get_partner_user(request)
        if partner_user:
            memorial = get_object_or_404(
                Memorial, 
                pk=memorial_id,
                partner=partner_user.partner  # ← КРИТИЧЕСКО ВАЖНО!
            )
            return memorial
        
        # Для семьи (через токен)
        if hasattr(request, 'family_invite'):
            invite = request.family_invite
            if invite.memorial.id != int(memorial_id):
                return Response(
                    {'detail': 'Токен не для этого мемориала'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            return invite.memorial
        
        return Response(
            {'detail': 'Нет прав доступа'}, 
            status=status.HTTP_403_FORBIDDEN
        )

class MediaList(APIView):
    authentication_classes = []
    permission_classes = []
    
    def get(self, request, memorial_id):
        memorial = get_object_or_404(Memorial, pk=memorial_id, status='active')
        qs = memorial.assets.filter(is_public=True).order_by('-created_at')
        data = [{
            'id': a.id, 
            'kind': a.kind, 
            'mime_type': a.mime_type, 
            'size_bytes': a.size_bytes, 
            'original_filename': a.original_filename
        } for a in qs]
        return Response(data)

class MediaDelete(APIView):
    permission_classes = [IsPartnerOrFamily]
    
    def delete(self, request, asset_id):
        # Сначала получаем ассет
        asset = get_object_or_404(MediaAsset, pk=asset_id)
        
        # Проверяем права на мемориал этого ассета
        memorial = self._get_memorial_with_permission_check(request, asset.memorial_id)
        if isinstance(memorial, Response):
            return memorial
        
        # Убедимся, что это тот же мемориал
        if memorial.id != asset.memorial_id:
            return Response(
                {'detail': 'Нет прав на удаление этого файла'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        size = asset.size_bytes
        memorial_id = asset.memorial_id
        
        with transaction.atomic():
            asset.delete()
            Memorial.objects.filter(pk=memorial_id).update(storage_bytes_used=F('storage_bytes_used') - size)
        
        return Response(status=204)
    
    def _get_memorial_with_permission_check(self, request, memorial_id):
        """Тот же метод проверки прав (можно вынести в отдельный модуль)"""
        partner_user = get_partner_user(request)
        if partner_user:
            memorial = get_object_or_404(
                Memorial, 
                pk=memorial_id,
                partner=partner_user.partner
            )
            return memorial
        
        if hasattr(request, 'family_invite'):
            invite = request.family_invite
            if invite.memorial.id != int(memorial_id):
                return Response(
                    {'detail': 'Токен не для этого мемориала'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            return invite.memorial
        
        return Response(
            {'detail': 'Нет прав доступа'}, 
            status=status.HTTP_403_FORBIDDEN
        )