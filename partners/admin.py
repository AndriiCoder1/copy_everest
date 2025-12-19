from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib import messages
from .models import Partner, PartnerUser

class PartnerUserForm(forms.ModelForm):
    # Поле для пароля (обязательное при создании)
    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
        required=False,  # Не обязательно при редактировании существующего
        help_text="Минимум 8 символов"
    )
    
    password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
        required=False,  # Не обязательно при редактировании существующего
        help_text="Введите тот же пароль для подтверждения"
    )
    
    class Meta:
        model = PartnerUser
        fields = ['partner', 'email', 'password1', 'password2', 'role']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'user@example.com'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # При редактировании существующего пользователя, не требуем пароль
        if self.instance.pk:
            self.fields['password1'].required = False
            self.fields['password2'].required = False
            self.fields['password1'].help_text = "Оставьте пустым, если не хотите менять пароль"
            self.fields['password2'].help_text = "Оставьте пустым, если не хотите менять пароль"
        else:
            # При создании нового - пароль обязателен
            self.fields['password1'].required = True
            self.fields['password2'].required = True
    
    def clean_email(self):
        """Проверка уникальности email"""
        email = self.cleaned_data.get('email')
        
        # Проверяем, нет ли уже PartnerUser с таким email
        if self.instance.pk:  # редактирование существующего
            if PartnerUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise ValidationError("Этот email уже используется другим сотрудником")
        else:  # создание нового
            if PartnerUser.objects.filter(email=email).exists():
                raise ValidationError("Этот email уже используется другим сотрудником")
        
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Проверяем пароли только если они указаны
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 or password2:  # Если хотя бы одно поле пароля заполнено
            if password1 != password2:
                raise ValidationError({'password2': "Пароли не совпадают"})
            
            if len(password1) < 8:
                raise ValidationError({'password1': "Пароль должен содержать минимум 8 символов"})
        
        return cleaned_data
    
    def save(self, commit=True):
        partner_user = super().save(commit=False)
        
        email = self.cleaned_data.get('email')
        password1 = self.cleaned_data.get('password1')
        
        # 1. Создаем или обновляем пользователя Django
        try:
            # Ищем существующего пользователя Django
            user = User.objects.get(email=email)
            
            # Обновляем пароль, если он указан
            if password1:
                user.set_password(password1)
                user.save()
                
        except User.DoesNotExist:
            # Создаем нового пользователя Django
            user = User.objects.create_user(
                username=email,  # используем email как username
                email=email,
                password=password1,  # пароль обязателен при создании
                is_staff=True,       # доступ в админку
                is_superuser=False,  # НЕ суперпользователь!
                first_name='',       # можно добавить поля из PartnerUser
                last_name=''
            )
        
        # 2. Сохраняем хеш пароля в PartnerUser (если пароль указан)
        if password1:
            partner_user.password_hash = make_password(password1)
        
        if commit:
            partner_user.save()
            
            # 3. Связываем PartnerUser с User (если в модели есть поле user)
            # Если в вашей модели нет поля user, эту часть можно убрать
            try:
                if hasattr(PartnerUser, 'user'):
                    partner_user.user = user
                    partner_user.save(update_fields=['user'])
            except:
                pass  # если нет поля user или другая ошибка
        
        return partner_user

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'billing_email', 'created_at')
    search_fields = ('name', 'billing_email')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(id=partner_user.partner.id)
        except PartnerUser.DoesNotExist:
            return qs.none()
    
    def has_add_permission(self, request):
        return request.user.is_superuser

@admin.register(PartnerUser)
class PartnerUserAdmin(admin.ModelAdmin):
    form = PartnerUserForm
    list_display = ('id', 'partner', 'email', 'role', 'created_at', 'get_user_status', 'get_login_info')
    search_fields = ('email', 'partner__name')
    list_filter = ('role', 'partner')
    
    def get_user_status(self, obj):
        """Показывает, может ли сотрудник войти в систему"""
        try:
            user = User.objects.get(email=obj.email)
            if user.is_active:
                return "✅ Может войти"
            else:
                return "❌ Не активен"
        except User.DoesNotExist:
            return "⚠️ Нет учетной записи"
    get_user_status.short_description = 'Статус входа'
    
    def get_login_info(self, obj):
        """Показывает логин для входа"""
        return f"Логин: {obj.email}"
    get_login_info.short_description = 'Данные для входа'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        try:
            partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(partner=partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()
    
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
                    # Автоматически назначаем своего партнера при создании
                    if not obj:  # если создаем нового пользователя
                        form.base_fields['partner'].initial = partner_user.partner
                        form.base_fields['partner'].disabled = True
                except PartnerUser.DoesNotExist:
                    form.base_fields['partner'].queryset = form.base_fields['partner'].queryset.none()
        
        return form
    
    def save_model(self, request, obj, form, change):
        # Добавляем сообщение о создании пользователя
        if not change:  # если создаем нового
            messages.success(
                request, 
                f'Сотрудник {obj.email} создан. Для входа используйте email и указанный пароль.'
            )
        
        super().save_model(request, obj, form, change)
    
    def response_add(self, request, obj, post_url_continue=None):
        """Переопределяем ответ после создания"""
        response = super().response_add(request, obj, post_url_continue)
        
        # Добавляем всплывающее сообщение
        messages.info(
            request,
            f'✅ Создан сотрудник {obj.email}. '
            f'Для входа в систему используйте: '
            f'Email: {obj.email}, пароль: указанный при создании.'
        )
        
        return response