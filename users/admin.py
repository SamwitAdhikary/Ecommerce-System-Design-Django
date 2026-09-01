from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from unfold.admin import ModelAdmin
from .models import User

class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users in Django Admin.
    Overrides default UserCreationForm to use email instead of username.
    """
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email',)

class CustomUserChangeForm(UserChangeForm):
    """
    Form for updating existing users in Django Admin.
    """
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = (
        'email', 
        'first_name', 
        'last_name', 
        'phone_number', 
        'wallet_balance', 
        'is_staff', 
        'is_active', 
        'date_joined'
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)
    readonly_fields = ('last_login', 'date_joined')

    # Detail / Change view fieldsets
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'phone_number', 'google_id', 'wallet_balance')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    
    # "Add User" creation view fieldsets
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
