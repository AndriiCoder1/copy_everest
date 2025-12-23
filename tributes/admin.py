from django.contrib.auth.models import User
from django.contrib import admin
from django import forms
from django.core.exceptions import PermissionDenied
from .models import Tribute
from partners.models import PartnerUser
from memorials.models import Memorial
from django.contrib import messages
from django.utils import timezone
from django.shortcuts import redirect

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
        """Protection against creating objects for other partner's memorials"""
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


@admin.register(Tribute)
class TributeAdmin(MemorialRelatedAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'memorial', 'author_name', 'status', 'created_at', 'approved_at')
    list_filter = ('status',)
    search_fields = ('author_name', 'message', 'memorial__first_name', 'memorial__last_name')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter ForeignKey fields for Tribute"""
        # Filter for moderated_by_user field
        if db_field.name == "moderated_by_user":
            if request.user.is_superuser:
                # Суперадмин видит всех пользователей
                kwargs["queryset"] = User.objects.all()
            else:
                try:
                    # Партнер видит только своих сотрудников
                    partner_user = PartnerUser.objects.get(email=request.user.email)
                    partner = partner_user.partner
                    
                    # Получаем всех PartnerUser этого партнера
                    partner_users = PartnerUser.objects.filter(partner=partner)
                    # Получаем соответствующих User
                    user_emails = [pu.email for pu in partner_users]
                    kwargs["queryset"] = User.objects.filter(email__in=user_emails)
                except PartnerUser.DoesNotExist:
                    kwargs["queryset"] = User.objects.none()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Можно добавить actions для массового одобрения/отклонения
    actions = ['approve_selected', 'reject_selected']
    
    def approve_selected(self, request, queryset):
        """Approve selected tributes"""
        for tribute in queryset:
            tribute.status = 'approved'
            tribute.approved_at = timezone.now()
            tribute.save()
        self.message_user(request, f"{queryset.count()} {self.model._meta.verbose_name} approved.")
    approve_selected.short_description = "Approve selected"
    
    def reject_selected(self, request, queryset):
        """Reject selected tributes"""
        queryset.update(status='rejected')
        self.message_user(request, f"{queryset.count()} {self.model._meta.verbose_name} rejected.")
    reject_selected.short_description = "Reject selected"
