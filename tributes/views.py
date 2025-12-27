from django.shortcuts import render, get_object_or_404, redirect  # <-- Добавьте 'redirect' в импорт
from django.utils import timezone  # <-- Добавьте этот импорт для работы с датами
from memorials.models import FamilyInvite
from .models import Tribute

def family_moderation_view(request, short_code):
    """Страница модерации трибьютов для семьи"""
    token = request.GET.get('token')
    
    if not token:
        return render(request, 'tributes/error.html', {'error': 'Требуется токен доступа'})
    
    # Проверяем токен - ИСПРАВЛЕННАЯ СТРОКА:
    try:
        # Ищем приглашение, которое еще не использовано и не просрочено
        invite = FamilyInvite.objects.get(
            token=token,
            consumed_at__isnull=True,          # Приглашение еще не использовано
            expires_at__gt=timezone.now()      # Срок действия еще не истек
        )
        memorial = invite.memorial
        
        # Получаем трибьюты, ожидающие модерации
        pending_tributes = Tribute.objects.filter(
            memorial=memorial,
            status='pending'
        ).order_by('-created_at')
        
        # Получаем уже одобренные трибьюты (для просмотра)
        approved_tributes = Tribute.objects.filter(
            memorial=memorial,
            status='approved'
        ).order_by('-created_at')[:10]
        
        if request.method == 'POST':
            # Обработка действий семьи
            tribute_id = request.POST.get('tribute_id')
            action = request.POST.get('action')
            
            tribute = get_object_or_404(Tribute, id=tribute_id, memorial=memorial)
            
            if action == 'approve':
                tribute.status = 'approved'
                tribute.save()
            elif action == 'reject':
                tribute.status = 'rejected'
                tribute.save()
            
            # Перенаправляем, чтобы избежать повторной отправки формы
            return redirect(f'{request.path}?token={token}')
        
        return render(request, 'tributes/family_moderation.html', {
            'memorial': memorial,
            'pending_tributes': pending_tributes,
            'approved_tributes': approved_tributes,
            'token': token,
        })
        
    except FamilyInvite.DoesNotExist:
        return render(request, 'templates/tributes/error.html', {'error': 'Неверный, использованный или просроченный токен доступа'})