from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone

from everest.permissions import IsPartnerOrFamily, get_partner_user
from memorials.models import Memorial
from .models import Tribute
from .serializers import TributeSubmitSerializer, TributeModerationSerializer

class TributePublicSubmit(APIView):
    authentication_classes = []
    permission_classes = []
    
    def post(self, request, code):
        memorial = get_object_or_404(Memorial, short_code=code, status='active')
        serializer = TributeSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tribute = Tribute.objects.create(memorial=memorial, **serializer.validated_data)
        return Response({'id': tribute.id, 'status': tribute.status}, status=status.HTTP_201_CREATED)

class TributeListModeration(APIView):
    permission_classes = [IsPartnerOrFamily]
    
    def get(self, request, memorial_id):
        # Проверяем права на мемориал
        memorial = self._get_memorial_with_permission_check(request, memorial_id)
        if isinstance(memorial, Response):
            return memorial
        
        status_q = request.query_params.get('status', 'pending')
        qs = Tribute.objects.filter(memorial=memorial, status=status_q).order_by('-created_at')
        data = TributeModerationSerializer(qs, many=True).data
        return Response(data)

class TributeApprove(APIView):
    permission_classes = [IsPartnerOrFamily]
    
    def post(self, request, tribute_id):
        tribute = get_object_or_404(Tribute, pk=tribute_id)
        
        # Проверяем права на мемориал этого соболезнования
        memorial = self._get_memorial_with_permission_check(request, tribute.memorial_id)
        if isinstance(memorial, Response):
            return memorial
        
        # Убедимся, что это тот же мемориал
        if memorial.id != tribute.memorial_id:
            return Response(
                {'detail': 'Нет прав на модерацию этого соболезнования'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        tribute.status = 'approved'
        tribute.approved_at = timezone.now()
        pu = get_partner_user(request)
        if pu:
            tribute.moderated_by_user = pu
        tribute.save(update_fields=['status','approved_at'])
        return Response({'status': tribute.status})

class TributeReject(APIView):
    permission_classes = [IsPartnerOrFamily]
    
    def post(self, request, tribute_id):
        tribute = get_object_or_404(Tribute, pk=tribute_id)
        
        # Проверяем права на мемориал этого соболезнования
        memorial = self._get_memorial_with_permission_check(request, tribute.memorial_id)
        if isinstance(memorial, Response):
            return memorial
        
        # Убедимся, что это тот же мемориал
        if memorial.id != tribute.memorial_id:
            return Response(
                {'detail': 'Нет прав на модерацию этого соболезнования'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        tribute.status = 'rejected'
        pu = get_partner_user(request)
        if pu:
            tribute.moderated_by_user = pu
        tribute.save(update_fields=['status'])
        return Response({'status': tribute.status})
    
    def _get_memorial_with_permission_check(self, request, memorial_id):
        """Общий метод проверки прав на мемориал"""
        partner_user = get_partner_user(request)
        if partner_user:
            memorial = get_object_or_404(
                Memorial, 
                pk=memorial_id,
                partner=partner_user.partner  # ← КРИТИЧЕСКО ВАЖНО!
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