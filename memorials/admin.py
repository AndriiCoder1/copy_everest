from django.contrib.auth.models import User
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
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

# ===== БАЗОВЫЙ МИКСИН ДЛЯ ВСЕХ МОДЕЛЕЙ С Memorial =====
class MemorialRelatedAdminMixin:
    """
    Mixin for all models with ForeignKey on Memorial
    Provides isolation by partner
    """
    
    def get_partner_user(self, request):
        """Get partner_user for current user"""
        try:
            return PartnerUser.objects.get(email=request.user.email)
        except PartnerUser.DoesNotExist:
            return None
    
    def get_queryset(self, request):
        """Filter objects by partner"""
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
        
        partner_user = self.get_partner_user(request)
        if partner_user:
            return qs.filter(memorial__partner=partner_user.partner)
        
        return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter dropdown list of memorial"""
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
        """Handle initial data with memorial_id from GET parameter"""
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
        """Protect against creating objects for other memorials"""
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
                            f"You do not have access to this memorial to create {self.model._meta.verbose_name}."
                        )
                        # Редирект на список объектов текущей модели
                        app_label = self.model._meta.app_label
                        model_name = self.model._meta.model_name
                        return redirect(f'admin:{app_label}_{model_name}_changelist')
                else:
                    messages.error(request, "You do not have partner rights.")
                    return redirect('admin:index')
        
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def save_model(self, request, obj, form, change):
        """Check partner rights when saving object"""
        if not request.user.is_superuser and hasattr(obj, 'memorial'):
            partner_user = self.get_partner_user(request)
            
            if partner_user:
                # Проверяем, что мемориал принадлежит партнеру
                if obj.memorial.partner != partner_user.partner:
                    raise PermissionDenied(
                        f"You do not have access to this memorial to create {self.model._meta.verbose_name}."
                    )
        
        super().save_model(request, obj, form, change)

@admin.register(Memorial)
class MemorialAdmin(admin.ModelAdmin):
    list_display = ('id','partner','last_name','status','short_code','storage_bytes_used','storage_bytes_limit', 'public_qr_link', 'family_invite_info')  
    readonly_fields = ('public_qr_link', 'family_invite_info') 
    

    actions = ['generate_qr_codes_action']

    def public_qr_link(self, obj):
        """Displays a public QR code and link""" 
        if obj.status == 'active' and hasattr(obj, 'qrcode') and obj.qrcode.qr_png:
            public_url = f"http://172.20.10.4:8000/m/{obj.short_code}/" 
            return format_html(
                '<strong>Public Access (for memorial):</strong><br>'
                '<img src="{}" style="max-height: 100px; border: 1px solid #ccc;"/><br>'
                '<small><a href="{}" target="_blank">{}</a></small>',
                obj.qrcode.qr_png.url,
                public_url,
                public_url
            )
        return "Memorial is not active or QR code is not created."
    public_qr_link.short_description = "QR for guests"

    def family_invite_info(self, obj):
        """Displays information for inviting family and token"""
        try:
            # Ищем активное приглашение
            invite = obj.familyinvite_set.filter(is_active=True).first()
            if invite:
                family_url = f"http://172.20.10.4:8000/memorials/{obj.short_code}/moderate/?token={invite.token}"
                return format_html(
                    '<strong>Family Access (with token):</strong><br>'
                    'Link: <a href="{}" target="_blank">{}</a><br>'
                    'Token: <code>{}</code><br>'
                    '<small>Send this link to your family. Do not post on the memorial.</small>',
                    family_url,
                    "Family moderation link",
                    invite.token
                )
        except Exception:
            pass
        return format_html(
            '<a href="{}">Send invitation to family</a>',
            reverse('admin:memorials_familyinvite_add') + f'?memorial_id={obj.id}'
        )
    family_invite_info.short_description = "Family Access Info"

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
    list_display = ('id', 'memorial', 'get_kind_display', 'file_size_display', 'is_public', 'created_at')
    list_filter = ('kind', 'is_public', 'created_at')
    readonly_fields = ('file_size_display', 'dimensions_display')
    search_fields = ('memorial__first_name', 'memorial__last_name', 'original_filename')
    
    def get_kind_display(self, obj):
        """Human-readable display for kind"""
        kinds = {
            'photo': 'Photo',
            'document': 'Document',
            'video': 'Video',
            'audio': 'Audio'
        }
        return kinds.get(obj.kind, obj.kind)
    get_kind_display.short_description = "Type"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter ForeignKey fields"""
        # Вызываем метод миксина для фильтрации memorial
        if db_field.name == "memorial":
            return super().formfield_for_foreignkey(db_field, request, **kwargs)
        
        # Фильтрация для поля uploaded_by_user
        if db_field.name == "uploaded_by_user":
            if request.user.is_superuser:
                # Суперадмин видит всех пользователей
                kwargs["queryset"] = PartnerUser.objects.all()
            else:
                try:
                    # Партнер видит только своих сотрудников
                    current_partner_user = PartnerUser.objects.get(email=request.user.email)
                    partner = current_partner_user.partner
                    # Фильтруем PartnerUser по партнеру
                    kwargs["queryset"] = PartnerUser.objects.filter(partner=partner) 
                except PartnerUser.DoesNotExist:
                    kwargs["queryset"] = PartnerUser.objects.none()  
            
            
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def file_size_display(self, obj):
        """Display file size in readable format"""
        if obj.size_bytes:
            size = obj.size_bytes
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return "N/A"
    file_size_display.short_description = "File size"
    
    def dimensions_display(self, obj):
        """Display image dimensions"""
        if obj.width and obj.height:
            return f"{obj.width}×{obj.height}px"
        return "N/A"
    dimensions_display.short_description = "Dimensions"
    
            
# Методы из миксина уже обеспечивают фильтрацию по memorial__partner
@admin.register(QRCode)
class QRCodeAdmin(MemorialRelatedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'memorial', 'version', 'qr_png_preview', 'created_at')
    list_filter = ('version',)
    readonly_fields = ('qr_png_preview',)
    
    def qr_png_preview(self, obj):
        if obj.qr_png and hasattr(obj.qr_png, 'url'):
            return format_html('<img src="{}" height="50" />', obj.qr_png.url)
        return "No image" 
    qr_png_preview.short_description = "QR Preview"
    
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
    list_display = ('id', 'asset', 'get_preset_display', 'size_bytes_display')
    list_filter = ('preset',)
    
    # Добавляем human-readable отображение для preset
    def get_preset_display(self, obj):
        """Human-readable display for preset"""
        presets = {
            'thumbnail_small': 'Small (150×150)',
            'thumbnail_medium': 'Medium (300×300)',
            'thumbnail_large': 'Large (600×600)',
            'preview': 'Preview',
            'original': 'Original'
        }
        return presets.get(obj.preset, obj.preset)
    get_preset_display.short_description = "Preset"

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
    size_bytes_display.short_description = "Size"
    
    def get_queryset(self, request):
        """Filter through asset__memorial__partner"""
        qs = super().get_queryset(request)
        
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(asset__memorial__partner=partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter ForeignKey field asset (relation with MediaAsset)"""
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

def partner_user_display(self):
    return f"{self.email} ({self.partner.name})"    

PartnerUser.__str__ = partner_user_display