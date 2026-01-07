from django.contrib import admin
from .models import AuditLog
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

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
        """Filters logs so that a partner can only see their own objects."""
        qs = super().get_queryset(request)
        
        # Superuser видит всё
        if request.user.is_superuser:
            return qs
        
        # Пытаемся получить объект партнёра для текущего пользователя
        try:
            from partners.models import PartnerUser
            partner_user = PartnerUser.objects.get(email=request.user.email)
        except PartnerUser.DoesNotExist:
            # Если пользователь не партнёр, не показываем ему логи
            return qs.none()
        
        partner = partner_user.partner
        
        # ДЛЯ ОТЛАДКИ: выводим в консоль информацию о партнёре
        #print(f"\n=== DEBUG: AuditLogAdmin.get_queryset ===")
        #print(f"Partner: {partner.name} (ID: {partner.id})")
        
        # Импортируем модели (делаем это здесь, чтобы избежать циклических импортов)
        from memorials.models import Memorial
        from assets.models import MediaAsset
        from tributes.models import Tribute
        
        # 1. Получаем ID всех мемориалов этого партнёра
        partner_memorial_ids = list(Memorial.objects.filter(
            partner=partner
        ).values_list('id', flat=True))
        
        # 2. Получаем ID всех медиафайлов этого партнёра
        partner_media_ids = list(MediaAsset.objects.filter(
            memorial__partner=partner
        ).values_list('id', flat=True))
        
        # 3. Получаем ID всех трибутов этого партнёра
        partner_tribute_ids = list(Tribute.objects.filter(
            memorial__partner=partner
        ).values_list('id', flat=True))
        
        # ДЛЯ ОТЛАДКИ: выводим списки ID
        #print(f"Memorial IDs: {partner_memorial_ids}")
        #print(f"Media IDs: {partner_media_ids}")
        #print(f"Tribute IDs: {partner_tribute_ids}")
        
        # Строим комбинированный фильтр, но только для непустых списков
        q_objects = Q()
        
        if partner_memorial_ids:
            q_objects |= Q(target_type='memorial', target_id__in=partner_memorial_ids)
        
        if partner_media_ids:
            q_objects |= Q(target_type='media', target_id__in=partner_media_ids)
        
        if partner_tribute_ids:
            q_objects |= Q(target_type='tribute', target_id__in=partner_tribute_ids)
        
        # Если ни одного условия не добавлено, значит у партнёра нет объектов
        if q_objects == Q():
            #print("DEBUG: Partner has no objects, returning empty queryset")
            return qs.none()
        
        #print(f"DEBUG: Applying filter: {q_objects}")
        return qs.filter(q_objects)