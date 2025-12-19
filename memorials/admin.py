from django.contrib import admin
from .models import Memorial, FamilyInvite, LanguageOverride, QRCode
from partners.models import PartnerUser

@admin.register(Memorial)
class MemorialAdmin(admin.ModelAdmin):
    list_display = ('id','partner','last_name','status','short_code','storage_bytes_used','storage_bytes_limit')
    
    # 1. Фильтрация мемориалов
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(partner=partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()
    
    # 2. Фильтрация выпадающего списка партнеров
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        if not request.user.is_superuser:
            if 'partner' in form.base_fields:
                try:
                    partner_user = PartnerUser.objects.get(email=request.user.email)
                    # Показываем только своего партнера
                    form.base_fields['partner'].queryset = form.base_fields['partner'].queryset.filter(
                        id=partner_user.partner.id
                    )
                except PartnerUser.DoesNotExist:
                    form.base_fields['partner'].queryset = form.base_fields['partner'].queryset.none()
        
        return form

# Аналогично для других моделей...

@admin.register(FamilyInvite)
class FamilyInviteAdmin(admin.ModelAdmin):
    list_display = ('id','memorial','email','expires_at','consumed_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(memorial__partner=partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()

@admin.register(LanguageOverride)
class LanguageOverrideAdmin(admin.ModelAdmin):
    list_display = ('id','memorial','language_code','created_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(memorial__partner=partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()

@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ('id','memorial','version','created_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(memorial__partner=partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()