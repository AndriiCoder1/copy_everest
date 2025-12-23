from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.db.models import Max
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from .models import Memorial, FamilyInvite, LanguageOverride, QRCode
from assets.models import MediaAsset, MediaThumbnail 
from partners.models import PartnerUser


# ===== БАЗОВЫЙ МИКСИН ДЛЯ ВСЕХ МОДЕЛЕЙ С Memorial =====
class MemorialRelatedAdminMixin:
    """
    Миксин для всех моделей с ForeignKey на Memorial
    Обеспечивает изоляцию по партнерам
    """
    
    def get_partner_user(self, request):
        """Получение partner_user для текущего пользователя"""
        try:
            return PartnerUser.objects.get(email=request.user.email)
        except PartnerUser.DoesNotExist:
            return None
    
    def get_queryset(self, request):
        """Фильтрация объектов по партнеру"""
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
        
        partner_user = self.get_partner_user(request)
        if partner_user:
            return qs.filter(memorial__partner=partner_user.partner)
        
        return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Фильтрация выпадающего списка memorial"""
        if db_field.name == "memorial":
            if request.user.is_superuser:
                kwargs["queryset"] = Memorial.objects.all()
            else:
                partner_user = self.get_partner_user(request)
                if partner_user:
                    kwargs["queryset"] = Memorial.objects.filter(partner=partner_user.partner)
                else:
                    kwargs["queryset"] = Memorial.objects.none()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_changeform_initial_data(self, request):
        """Обработка initial данных с memorial_id из GET-параметра"""
        initial = super().get_changeform_initial_data(request)
        
        if 'memorial_id' in request.GET:
            memorial_id = request.GET.get('memorial_id')
            
            if request.user.is_superuser:
                initial['memorial'] = memorial_id
            else:
                partner_user = self.get_partner_user(request)
                if partner_user:
                    try:
                        memorial = Memorial.objects.get(
                            id=memorial_id, 
                            partner=partner_user.partner
                        )
                        initial['memorial'] = memorial_id
                    except Memorial.DoesNotExist:
                        pass
        
        return initial
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Защита от создания объектов для чужих мемориалов"""
        if request.method == 'GET' and 'memorial_id' in request.GET:
            memorial_id = request.GET.get('memorial_id')
            
            if not request.user.is_superuser:
                partner_user = self.get_partner_user(request)
                if partner_user:
                    try:
                        Memorial.objects.get(id=memorial_id, partner=partner_user.partner)
                    except Memorial.DoesNotExist:
                        messages.error(
                            request, 
                            f"У вас нет доступа к этому мемориалу для создания {self.model._meta.verbose_name}."
                        )
                        # Редирект на список объектов текущей модели
                        app_label = self.model._meta.app_label
                        model_name = self.model._meta.model_name
                        return redirect(f'admin:{app_label}_{model_name}_changelist')
                else:
                    messages.error(request, "У вас нет прав партнера.")
                    return redirect('admin:index')
        
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def save_model(self, request, obj, form, change):
        """Проверка прав при сохранении объекта"""
        if not request.user.is_superuser and hasattr(obj, 'memorial'):
            partner_user = self.get_partner_user(request)
            
            if partner_user:
                # Проверяем, что мемориал принадлежит партнеру
                if obj.memorial.partner != partner_user.partner:
                    raise PermissionDenied(
                        f"Нельзя создать/изменить {self.model._meta.verbose_name} для чужого мемориала"
                    )
        
        super().save_model(request, obj, form, change)

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
class FamilyInviteAdmin(MemorialRelatedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'memorial', 'email', 'expires_at', 'consumed_at')
    list_filter = ('expires_at', 'consumed_at')
    search_fields = ('email', 'memorial__first_name', 'memorial__last_name')
    
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
class LanguageOverrideAdmin(MemorialRelatedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'memorial', 'language_code', 'created_at')
    list_filter = ('language_code',)
    search_fields = ('memorial__first_name', 'memorial__last_name')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(memorial__partner=partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()


@admin.register(MediaAsset)
class MediaAssetAdmin(MemorialRelatedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'memorial', 'kind', 'file_size_display', 'is_public', 'created_at')
    list_filter = ('kind', 'is_public', 'created_at')
    readonly_fields = ('file_size_display', 'dimensions_display')
    search_fields = ('memorial__first_name', 'memorial__last_name', 'original_filename')
    
    def file_size_display(self, obj):
        """Отображение размера файла в читаемом формате"""
        if obj.size_bytes:
            size = obj.size_bytes
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return "N/A"
    file_size_display.short_description = "Размер файла"
    
    def dimensions_display(self, obj):
        """Отображение размеров изображения"""
        if obj.width and obj.height:
            return f"{obj.width}×{obj.height}px"
        return "N/A"
    dimensions_display.short_description = "Размеры"
    
    # Методы из миксина уже обеспечивают фильтрацию по memorial__partner            

@admin.register(QRCode)
class QRCodeAdmin(MemorialRelatedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'memorial', 'version', 'qr_png_preview', 'created_at')
    list_filter = ('version',)
    readonly_fields = ('qr_png_preview',)
    
    def qr_png_preview(self, obj):
        if obj.qr_png and hasattr(obj.qr_png, 'url'):
            return format_html('<img src="{}" height="50" />', obj.qr_png.url)
        return "Нет изображения"
    qr_png_preview.short_description = "Предпросмотр QR"
    
    def save_model(self, request, obj, form, change):
        # Сначала устанавливаем версию
        if not obj.version:
            max_version = QRCode.objects.filter(
                memorial=obj.memorial
            ).aggregate(Max('version'))['version__max'] or 0
            obj.version = max_version + 1
    
        # Затем вызываем save_model миксина
        super().save_model(request, obj, form, change)

@admin.register(MediaThumbnail)
class MediaThumbnailAdmin(admin.ModelAdmin):
    list_display = ('id', 'asset', 'preset', 'size_bytes_display')
    list_filter = ('preset',)
    
    def size_bytes_display(self, obj):
        if obj.size_bytes:
            size = obj.size_bytes
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return "N/A"
    size_bytes_display.short_description = "Размер"
    
    def get_queryset(self, request):
        """Фильтрация через asset__memorial__partner"""
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(asset__memorial__partner=partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Фильтруем выпадающий список asset (связь с MediaAsset)"""
        if db_field.name == "asset":
            if request.user.is_superuser:
                kwargs["queryset"] = MediaAsset.objects.all()
            else:
                try:
                    partner_user = PartnerUser.objects.get(email=request.user.email)
                    kwargs["queryset"] = MediaAsset.objects.filter(memorial__partner=partner_user.partner)
                except PartnerUser.DoesNotExist:
                    kwargs["queryset"] = MediaAsset.objects.none()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)    