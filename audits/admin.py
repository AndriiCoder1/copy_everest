from django.contrib import admin
from django.db.models import Q 
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'action', 'actor_display', 'target_type', 'target_id', 'created_at')
    list_filter = ('action', 'actor_type', 'target_type', 'created_at')
    search_fields = ('actor_id', 'target_id', 'metadata', 'target_type')
    date_hierarchy = 'created_at'

    def actor_display(self, obj):
        return obj.get_actor_display()
    actor_display.short_description = 'Actor'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Суперадмин видит всё
        if request.user.is_superuser:
            return qs
        
        # Партнер видит только логи своих мемориалов
        try:
            from partners.models import PartnerUser
            from memorials.models import Memorial
            from assets.models import MediaAsset  # <-- Импортируем модель MediaAsset

            partner_user = PartnerUser.objects.get(email=request.user.email)
            partner = partner_user.partner

            # 1. Получаем ВСЕ ID мемориалов этого партнёра
            partner_memorial_ids = Memorial.objects.filter(
                partner=partner
            ).values_list('id', flat=True)

            # 2. Получаем ВСЕ ID медиа-ассетов, привязанных к этим мемориалам
            partner_media_ids = MediaAsset.objects.filter(
                memorial__partner=partner
            ).values_list('id', flat=True)

            # 3. Создаём фильтр: логи для мемориалов партнёра ИЛИ для медиафайлов его мемориалов
            
            partner_filter = Q(target_type='memorial', target_id__in=partner_memorial_ids) | \
                             Q(target_type='media', target_id__in=partner_media_ids)

            return qs.filter(partner_filter)

        except PartnerUser.DoesNotExist:
            # Если это не партнёр, возвращаем пустой QuerySet
            return qs.none()