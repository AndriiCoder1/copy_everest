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
from memorials.models import Memorial, FamilyInvite
from .models import MediaAsset
import threading

# Простое хранилище для контекста аудита
_audit_context = threading.local()

def set_audit_context(request):
    """Устанавливает контекст для аудита"""
    context = {
        'actor_type': 'system',
        'actor_id': None,
        'family_token': None,
        'token_preview': None,
    }
    
    # Проверяем семейный токен
    token = request.headers.get('X-Family-Token') or request.GET.get('token')
    if token:
        context.update({
            'actor_type': 'family',
            'family_token': token,
            'token_preview': f"{token[:8]}..." if len(token) > 8 else token,
        })
    # Проверяем партнера
    elif request.user.is_authenticated:
        if hasattr(request.user, 'partneruser'):
            context.update({
                'actor_type': 'partner_user',
                'actor_id': request.user.id,
            })
    
    _audit_context.value = context

def get_audit_context():
    """Получает контекст для аудита"""
    return getattr(_audit_context, 'value', {})

def clear_audit_context():
    """Очищает контекст аудита"""
    if hasattr(_audit_context, 'value'):
        delattr(_audit_context, 'value')

ALLOWED_MIME = {'image/jpeg','image/png','image/webp','application/pdf'}

# API для загрузки медиафайлов (фотографий, видео)
class MediaUpload(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsPartnerOrFamily]
    
    def post(self, request, memorial_id):
        # ⚡ Устанавливаем контекст ДО всего
        set_audit_context(request)
        
        try:
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
                
                # Проверка на дубликаты (по мемориалу, а не глобально)
                if MediaAsset.objects.filter(memorial=memorial, checksum_sha256=checksum).exists():
                    return Response({'detail':'duplicate in this memorial'}, status=status.HTTP_409_CONFLICT)
                
                # ⚡ СОЗДАЕМ АССЕТ ТОЛЬКО ОДИН РАЗ
                asset = MediaAsset.objects.create(
                    memorial=memorial,
                    kind='image' if file.content_type.startswith('image/') else 'document',
                    file=file,
                    original_filename=file.name,
                    mime_type=file.content_type,
                    size_bytes=size,
                    checksum_sha256=checksum,
                    is_public=True,
                )
                Memorial.objects.filter(pk=memorial.pk).update(storage_bytes_used=F('storage_bytes_used') + size)
            
            # ⚡ ЛОГИРУЕМ ПОСЛЕ УСПЕШНОГО СОЗДАНИЯ
            self._log_media_upload(asset)
            
            return Response({'id': asset.id}, status=status.HTTP_201_CREATED)
            
        finally:
            # ⚡ ОЧИЩАЕМ КОНТЕКСТ В ЛЮБОМ СЛУЧАЕ
            clear_audit_context()
    
    def _log_media_upload(self, asset):
        """Ручное логирование загрузки медиа"""
        from audits.models import AuditLog
        
        context = get_audit_context()
        metadata = {
            'memorial_id': asset.memorial.id,
            'file_type': asset.kind,
            'file_size': asset.size_bytes,
        }
        
        if context.get('family_token'):
            metadata['token_preview'] = context['token_preview']
            # Пытаемся найти FamilyInvite
            try:
                invite = FamilyInvite.objects.get(token=context['family_token'])
                metadata['family_invite_id'] = invite.id
                metadata['family_email'] = invite.email
            except FamilyInvite.DoesNotExist:
                pass

         # ⚡ СОЗДАЕМ ЛОГ
        AuditLog.objects.create(
            actor_type=context.get('actor_type', 'system'),
            actor_id=context.get('actor_id'),
            action='upload_media',
            target_type='media',
            target_id=asset.id,
            metadata=metadata
        )

    def _get_memorial_with_permission_check(self, request, memorial_id):
        """Check permissions for accessing a memorial"""
        # For partner
        partner_user = get_partner_user(request)
        if partner_user:
            memorial = get_object_or_404(
                Memorial, 
                pk=memorial_id,
                partner=partner_user.partner  
            )
            return memorial
        
        # Для семьи (через токен)
        if hasattr(request, 'family_invite'):
            invite = request.family_invite
            if invite.memorial.id != int(memorial_id):
                return Response(
                    {'detail': 'Token not for this memorial'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            return invite.memorial
        
        return Response(
            {'detail': 'No access rights'}, 
            status=status.HTTP_403_FORBIDDEN
        )
# API для получения списка медиафайлов мемориала
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
# API для удаления медиафайла
class MediaDelete(APIView):
    permission_classes = [IsPartnerOrFamily]
    
    def delete(self, request, asset_id):
        # ⚡ Устанавливаем контекст ДО всего
        set_audit_context(request)
        
        try:
            # Сначала получаем ассет
            asset = get_object_or_404(MediaAsset, pk=asset_id)
        
            # Проверяем права на мемориал этого ассета
            memorial = self._get_memorial_with_permission_check(request, asset.memorial_id)
            if isinstance(memorial, Response):
                return memorial
        
            # Убедимся, что это тот же мемориал
            if memorial.id != asset.memorial_id:
                return Response(
                    {'detail': 'No rights to delete this file'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
            size = asset.size_bytes
            memorial_id = asset.memorial_id
        
            with transaction.atomic():
                asset.delete()
                Memorial.objects.filter(pk=memorial_id).update(storage_bytes_used=F('storage_bytes_used') - size)
            # ⚡ ЛОГИРУЕМ УДАЛЕНИЕ
            self._log_media_delete(asset)

            return Response(status=status.HTTP_204_NO_CONTENT)
        finally:
            # ⚡ ОЧИЩАЕМ КОНТЕКСТ
            clear_audit_context() 

    def _log_media_delete(self, asset):
        """Ручное логирование удаления медиа"""
        from audits.models import AuditLog
        
        context = get_audit_context()
        metadata = {
            'memorial_id': asset.memorial.id,
            'file_type': asset.kind,
            'file_size': asset.size_bytes,
        }
        
        if context.get('family_token'):
            metadata['token_preview'] = context['token_preview']
            try:
                invite = FamilyInvite.objects.get(token=context['family_token'])
                metadata['family_invite_id'] = invite.id
                metadata['family_email'] = invite.email
            except FamilyInvite.DoesNotExist:
                pass
        
        AuditLog.objects.create(
            actor_type=context.get('actor_type', 'system'),
            actor_id=context.get('actor_id'),
            action='delete_media',
            target_type='media',
            target_id=asset.id,
            metadata=metadata
        )           

    def _get_memorial_with_permission_check(self, request, memorial_id):
        """Check permissions for accessing a memorial"""
        # For partner
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
                    {'detail': 'Token not for this memorial'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            return invite.memorial
        
        return Response(
            {'detail': 'No access rights'}, 
            status=status.HTTP_403_FORBIDDEN
        )