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


class TributeAdminForm(forms.ModelForm):
    """Form with auto-filling fields""" 
    class Meta:
        model = Tribute
        
        exclude = ['moderated_by_user']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = kwargs.pop('request', None)
        
        # Если пользователь не суперадмин (т.е. партнер),
        # делаем поле статуса неактивным или скрываем.
        if request and not request.user.is_superuser:
            # Вариант А: Сделать поле readonly (рекомендуется)
            self.fields['status'].disabled = True
            # Или добавить подсказку
            self.fields['status'].help_text = 'Only administrators can change the status. The family moderates via the web interface.'

# ===== TributeAdmin =====
@admin.register(Tribute)
class TributeAdmin(MemorialRelatedAdminMixin, admin.ModelAdmin):
    form = TributeAdminForm
    list_display = ('id', 'memorial', 'author_name', 'status', 'created_at', 'approved_at', 'moderated_by_user')
    list_filter = ('status',) 
    search_fields = ('author_name', 'message', 'memorial__first_name', 'memorial__last_name')
    
    # Скрываем moderated_by_user из формы, так как он будет заполняться автоматически
    exclude = ['moderated_by_user']
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter ForeignKey fields for Tribute"""
        # ОРИГИНАЛЬНАЯ логика вашего миксина для поля memorial
        if db_field.name == "memorial":
            return super().formfield_for_foreignkey(db_field, request, **kwargs)
        
        # НОВАЯ логика: для moderated_by_user показываем только PartnerUser текущего партнера
        if db_field.name == "moderated_by_user":
            if request.user.is_superuser:
                kwargs["queryset"] = PartnerUser.objects.all()
            else:
                try:
                    partner_user = self.get_partner_user(request)
                    if partner_user:
                        kwargs["queryset"] = PartnerUser.objects.filter(partner=partner_user.partner)
                    else:
                        kwargs["queryset"] = PartnerUser.objects.none()
                except Exception:
                    kwargs["queryset"] = PartnerUser.objects.none()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_readonly_fields(self, request, obj=None):
        """Making the status field read-only for partners""" 
        readonly_fields = list(super().get_readonly_fields(request, obj) or [])
        if not request.user.is_superuser:
            readonly_fields.append('status')
        return readonly_fields

    def save_model(self, request, obj, form, change):
        """Overriding save for partners"""
        # Партнеры не могут менять статус через админку
        if not request.user.is_superuser and 'status' in form.changed_data:
            # Восстанавливаем исходный статус
            if change:
                obj.status = Tribute.objects.get(pk=obj.pk).status
            else:
                obj.status = 'pending' 
        elif not change and not request.user.is_superuser:
            # Для новых трибьютов от партнеров (если статус не менялся явно)
            obj.status = 'pending'        
    
        super().save_model(request, obj, form, change)
        
    

    def approve_selected(self, request, queryset):
        """Approve selected tributes"""
        updated = 0
        for tribute in queryset:
            tribute.status = 'approved'
            tribute.approved_at = timezone.now()
            
            # Автоматически устанавливаем текущего пользователя как модератора
            try:
                partner_user = PartnerUser.objects.get(email=request.user.email)
                tribute.moderated_by_user = partner_user
            except PartnerUser.DoesNotExist:
                pass
            
            tribute.save()
            updated += 1
        
        self.message_user(request, f"{updated} {self.model._meta.verbose_name} approved.")
    approve_selected.short_description = "Approve selected"
    
    def reject_selected(self, request, queryset):
        """Reject selected tributes"""
        queryset.update(status='rejected')
        self.message_user(request, f"{queryset.count()} {self.model._meta.verbose_name} rejected.")
    reject_selected.short_description = "Reject selected"
