from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from unfold.admin import ModelAdmin, TabularInline
from .models import User, Address, WalletTransaction


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


class WalletTransactionInline(TabularInline):
    """
    Inline ledger history on User detail page in Django Admin.
    Immutable audit history (modifications blocked).
    """
    model = WalletTransaction
    extra = 1
    readonly_fields = ("order_id", "created_at")
    can_delete = False
    
    def has_change_permission(self, request, obj=None):
        # Prevents editing existing historical transactions in the inline
        return False


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
    inlines = [WalletTransactionInline]
    readonly_fields = ('wallet_balance', 'last_login', 'date_joined')

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


@admin.register(Address)
class AddressAdmin(ModelAdmin):
    list_display = ('user', 'city', 'state', 'pincode', 'is_default')
    list_filter = ('city', 'state', 'is_default')
    search_fields = ('user__email', 'address_line', 'city', 'pincode')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(ModelAdmin):
    list_display = ("user", "transaction_type", "amount", "order_id", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("user__email", "order_id", "description")

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing transaction is locked for audit integrity
            return ("user", "amount", "transaction_type", "order_id", "created_at")
        return ()
