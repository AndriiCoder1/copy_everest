from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib import messages
from .models import Partner, PartnerUser

# 1. Proxy модель для безопасного отображения
class PartnerUserProxy(PartnerUser):
    class Meta:
        proxy = True
        verbose_name = 'Partner User'
        verbose_name_plural = 'Partner Users'

# 2. Форма без поля partner
class PartnerUserForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
        required=False,
        help_text="Minimum 8 characters"
    )
    
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
        required=False,
        help_text="Enter the same password as before"
    )
    
    class Meta:
        model = PartnerUser
        fields = ['partner', 'email', 'password1', 'password2', 'role']  # NO 'partner' field!


    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['password1'].required = False
            self.fields['password2'].required = False
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.instance.pk:
            if PartnerUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise ValidationError("This email is already used by another staff member")
        else:
            if PartnerUser.objects.filter(email=email).exists():
                raise ValidationError("This email is already used by another staff member")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 or password2:
            if password1 != password2:
                raise ValidationError({'password2': "Passwords don't match"})
            if len(password1) < 8:
                raise ValidationError({'password1': "Password must be at least 8 characters"})
        return cleaned_data

# 3. Админка для Partner
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

# 4. Админка для PartnerUserProxy
@admin.register(PartnerUserProxy)
class PartnerUserAdmin(admin.ModelAdmin):
    form = PartnerUserForm
    list_display = ('id', 'partner', 'email', 'role', 'created_at')
    search_fields = ('email', 'partner__name')
    list_filter = ('role', 'partner')
    

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
    
        if not request.user.is_superuser and 'partner' in form.base_fields:
            form.base_fields['partner'].widget = forms.HiddenInput()
        
            # Автоматически заполняем партнером создателя
            try:
                creator_profile = PartnerUser.objects.get(email=request.user.email)
                form.base_fields['partner'].initial = creator_profile.partner
            except PartnerUser.DoesNotExist:
                pass
    
        return form


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            admin_partner_user = PartnerUser.objects.get(email=request.user.email)
            return qs.filter(partner=admin_partner_user.partner)
        except PartnerUser.DoesNotExist:
            return qs.none()
    
    
    
    def save_model(self, request, obj, form, change):
        """
        Автоматически создаем User при создании PartnerUser
        """
    
        # 1. Если это создание нового PartnerUser (не редактирование)
        if not change:
            # 2. Если создатель - суперадмин
            if request.user.is_superuser:
                # Суперадмин должен был выбрать партнера в форме
                if not obj.partner:
                    raise ValidationError("Partner must be selected when creating user as superadmin.")
        
            # 3. Если создатель - партнер-админ
            else:
                try:
                    # Находим профиль создателя
                    creator_profile = PartnerUser.objects.get(email=request.user.email)
                    obj.partner = creator_profile.partner
                except PartnerUser.DoesNotExist:
                    # Если у создателя нет профиля, ошибка
                    raise ValidationError("Cannot create user: your partner profile not found.")
    
        # 4. Сохраняем PartnerUser (это создаст запись в partners_partneruser)
        super().save_model(request, obj, form, change)
    
        # 5. Теперь создаем/обновляем User Django
        email = obj.email
        password = form.cleaned_data.get('password1') if hasattr(form, 'cleaned_data') else None
    
        try:
            # Ищем существующего User
            user = User.objects.get(email=email)
        
            # Обновляем пароль, если он указан
            if password:
                user.set_password(password)
                user.save()
                # Сохраняем хеш пароля в PartnerUser
                obj.password_hash = make_password(password)
                obj.save(update_fields=['password_hash'])
                
        except User.DoesNotExist:
            # Создаем нового User
            if not password:
                # Если пароль не указан, генерируем случайный
                import secrets
                password = secrets.token_urlsafe(12)
        
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                is_staff=True,
                is_superuser=False
            )
        
            # Сохраняем хеш пароля в PartnerUser
            obj.password_hash = make_password(password)
            obj.save(update_fields=['password_hash'])
    
    def response_add(self, request, obj, post_url_continue=None):
        """Добавляем сообщение после создания"""
        response = super().response_add(request, obj, post_url_continue)
        messages.success(
            request,
            f'✅ Partner user {obj.email} created successfully. '
            f'Login email: {obj.email}'
        )
        return response