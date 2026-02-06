from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from everest.permissions import IsPartnerOrFamily, get_partner_user
from memorials.models import Memorial
import logging
from .models import Tribute
from .tasks import moderate_tribute_with_ai
from .serializers import TributeSubmitSerializer, TributeModerationSerializer

logger = logging.getLogger(__name__)

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
        print(f"=== DEBUG: TributeListModeration.get() called with memorial_id={memorial_id} ===")
        print(f"=== DEBUG: Request headers: {dict(request.headers)} ===")
        # Проверяем права на мемориал
        memorial = self._get_memorial_with_permission_check(request, memorial_id)
        if isinstance(memorial, Response):
            return memorial
        
        status_q = request.query_params.get('status', 'pending')
        qs = Tribute.objects.filter(memorial=memorial, status=status_q).order_by('-created_at')
        data = TributeModerationSerializer(qs, many=True).data
        return Response(data)

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
                {'detail': 'No rights to moderate this tribute'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        tribute.status = 'approved'
        tribute.approved_at = timezone.now()
        pu = get_partner_user(request)
        if pu:
            tribute.moderated_by_user = pu
        tribute.save(update_fields=['status','approved_at'])
        return Response({'status': tribute.status})

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
                {'detail': 'No rights to moderate this tribute'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        tribute.status = 'rejected'
        pu = get_partner_user(request)
        if pu:
            tribute.moderated_by_user = pu
        tribute.save(update_fields=['status'])
        return Response({'status': tribute.status})

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

# AI-модерация
class TributeAIModerate(APIView):
    """
    API для запуска и управления AI-модерацией.
    Доступ: партнеры и семья (как и для обычной модерации).
    """
    permission_classes = [IsPartnerOrFamily]  # Используем ваши существующие права
    
    def post(self, request, tribute_id=None):
        """
        Запуск ИИ-модерации для трибьюта.
        POST /api/tributes/<id>/ai-moderate/ - для одного
        POST /api/tributes/ai-moderate/batch/ - пакетная (без ID)
        """
        if tribute_id:
            # 1. Модерация конкретного трибьюта
            tribute = get_object_or_404(Tribute, pk=tribute_id)
            
            # Проверяем права на мемориал (используем вашу существующую логику)
            memorial = self._get_memorial_with_permission_check(request, tribute.memorial_id)
            if isinstance(memorial, Response):
                return memorial
            
            # Проверяем, можно ли модерировать
            if tribute.status != 'pending':
                return Response(
                    {'error': 'Трибьют уже отмодерирован'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Проверяем, не запущена ли уже ИИ-модерация
            if tribute.ai_moderated_at:
                return Response({
                    'status': 'already_moderated',
                    'tribute_id': tribute.id,
                    'ai_verdict': tribute.ai_verdict,
                    'message': 'ИИ уже провёл модерацию этого трибьюта'
                })
            
            # Запускаем фоновую задачу
            try:
                task = moderate_tribute_with_ai.delay(tribute.id)
                return Response({
                    'status': 'moderation_started',
                    'tribute_id': tribute.id,
                    'task_id': task.id,
                    'message': 'ИИ-модерация запущена в фоне'
                })
            except ImportError:
                logger.error("Файл tasks.py с moderate_tribute_with_ai не найден")
                return Response(
                    {'error': 'Система ИИ-модерации ещё не настроена'},
                    status=status.HTP_503_SERVICE_UNAVAILABLE
                )
        
        else:
            # 2. Пакетная модерация (для админа/CRON)
            # Нужны дополнительные права - проверяем, что это партнер
            partner_user = get_partner_user(request)
            if not partner_user:
                return Response(
                    {'error': 'Только партнеры могут запускать пакетную модерацию'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Берём трибьюты только этого партнера
            pending_tributes = Tribute.objects.filter(
                memorial__partner=partner_user.partner,
                status='pending',
                ai_verdict='pending_ai'
            )[:10]  # Ограничиваем пакет
            
            task_ids = []
            for tribute in pending_tributes:
                try:
                    task = moderate_tribute_with_ai.delay(tribute.id)
                    task_ids.append(task.id)
                except Exception as e:
                    logger.error(f"Ошибка запуска ИИ-модерации для {tribute.id}: {e}")
            
            return Response({
                'status': 'batch_moderation_started',
                'count': len(pending_tributes),
                'tasks_started': len(task_ids),
                'task_ids': task_ids,
                'message': f'Запущена ИИ-модерация {len(task_ids)} трибьютов'
            })
    
    def get(self, request, tribute_id):
        """
        Получение результатов ИИ-модерации.
        GET /api/tributes/<id>/ai-moderate/
        """
        tribute = get_object_or_404(Tribute, pk=tribute_id)
        
        # Проверяем права на этот трибьют
        memorial = self._get_memorial_with_permission_check(request, tribute.memorial_id)
        if isinstance(memorial, Response):
            return memorial
        
        if not tribute.ai_moderation_result:
            return Response({
                'status': 'pending',
                'tribute_id': tribute.id,
                'message': 'ИИ-модерация ещё не выполнена'
            }, status=status.HTTP_202_ACCEPTED)
        
        # Форматируем ответ для клиента
        ai_data = tribute.ai_moderation_result
        response_data = {
            'tribute_id': tribute.id,
            'ai_verdict': tribute.ai_verdict,
            'ai_confidence': tribute.ai_confidence,
            'ai_moderated_at': tribute.ai_moderated_at,
            'analysis': {
                'reasoning': ai_data.get('reasoning'),
                'flags': ai_data.get('flags', []),
                'final_verdict': ai_data.get('verdict')
            },
            'current_status': tribute.status,
            'auto_action_taken': tribute.status in ['approved', 'rejected'] and 
                                 tribute.ai_confidence and tribute.ai_confidence > 0.85
        }
        
        return Response(response_data)
    
    # ===== ВАЖНО: Копируем ваш существующий метод проверки прав =====
    def _get_memorial_with_permission_check(self, request, memorial_id):
        """Check permissions for accessing a memorial (скопирован из TributeApprove)"""
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