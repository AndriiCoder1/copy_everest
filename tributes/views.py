from django.shortcuts import render, get_object_or_404, redirect  
from django.utils import timezone  
from memorials.models import FamilyInvite, Memorial
from .models import Tribute
from assets.models import MediaAsset
from audits.models import AuditLog
import hashlib
import json
from django.core.cache import cache

def family_full_view(request, short_code):
    token = request.GET.get('token')
    
    if not token:
        return render(request, 'tributes/error.html', 
                     {'error': 'Токен доступа обязателен'})
    
    try:
        # Ищем приглашение
        invite = FamilyInvite.objects.get(token=token)
        memorial = invite.memorial
        
        # Проверяем, что короткий код совпадает
        if memorial.short_code != short_code:
            return render(request, 'tributes/error.html',
                         {'error': 'Токен не соответствует мемориалу'})
        
        # ОБРАБОТКА POST-запроса (модерация) 
        if request.method == 'POST':
            tribute_id = request.POST.get('tribute_id')
            action = request.POST.get('action')
            
            if tribute_id and action in ['approve', 'reject']:
                tribute = get_object_or_404(Tribute, id=tribute_id, memorial=memorial)
                
                if action == 'approve':
                    tribute.status = 'approved'
                    old_status = 'pending'
                else:
                    tribute.status = 'rejected'
                    old_status = 'pending'
                
                # Устанавливаем флаг, чтобы сигнал пропустил логирование
                tribute._skip_audit_log = {
                    'moderated_by': 'family',
                    'invite_id': invite.id,
                    'email': invite.email,
                    'token_preview': f"{token[:8]}..."
                }
            
                # Логируем модерацию
                AuditLog.objects.create(
                    actor_type='family',
                    actor_id=None,
                    action='moderate_tribute',
                    target_type='tribute',
                    target_id=tribute.id,
                    metadata={
                        'memorial_id': memorial.id,
                        'old_status': old_status,
                        'new_status': tribute.status,
                        'family_invite_id': invite.id,
                        'family_email': invite.email,
                        'token_preview': f"{token[:8]}...",
                    }
                )
                
                tribute.save()
                
                # Перенаправляем, чтобы избежать повторной отправки формы
                return redirect(f'{request.path}?token={token}')
        
        # Логируем доступ
        AuditLog.objects.create(
            actor_type='family',
            actor_id=None,
            action='access_family_interface',
            target_type='memorial',
            target_id=memorial.id,
            metadata={
                'family_invite_id': invite.id,
                'family_email': invite.email,
                'token_preview': f"{token[:8]}...",
            }
        )
        
        # Получаем медиа-файлы мемориала
        assets = MediaAsset.objects.filter(memorial=memorial)
        
        # Получаем трибьюты
        pending_tributes = Tribute.objects.filter(
            memorial=memorial, status='pending'
        ).order_by('-created_at')
        
        approved_tributes = Tribute.objects.filter(
            memorial=memorial, status='approved'
        ).order_by('-created_at')
        
        return render(request, 'tributes/family_full_view.html', {
            'memorial': memorial,
            'assets': assets,
            'pending_tributes': pending_tributes,
            'approved_tributes': approved_tributes,
            'token': token,  
        })
        
    except FamilyInvite.DoesNotExist:
        return render(request, 'tributes/error.html', 
                     {'error': 'Неверный, использованный или просроченный токен доступа'})
    except Memorial.DoesNotExist:
        return render(request, 'tributes/error.html',
                     {'error': 'Мемориал не найден'})


