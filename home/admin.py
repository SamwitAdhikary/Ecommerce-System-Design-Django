from django.contrib import admin
from .models import SiteSettings, ShippingZone


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """
    Admin configuration for singleton site settings.
    Disallows adding multiple instances and prevents accidental deletion.
    """
    fieldsets = (
        ('Storefront Identity & Contact', {
            'fields': ('site_name', 'contact_email', 'contact_phone', 'address')
        }),
        ('Operations & Thresholds', {
            'fields': ('maintenance_mode', 'minimum_order_value')
        }),
        ('Global Shipping Policies', {
            'fields': ('standard_shipping_fee', 'free_shipping_threshold', 'is_zone_shipping_enabled')
        }),
        ('Cash On Delivery (COD) Rules', {
            'fields': ('cod_charge', 'partial_cod_deposit_percentage')
        }),
    )

    def has_add_permission(self, request):
        """Disallow adding a new row if a singleton record already exists."""
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton instance from Django admin."""
        return False


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    """
    Admin interface for managing regional shipping zones and state coverage.
    """
    list_display = (
        'name',
        'shipping_fee',
        'free_shipping_threshold',
        'cod_charge',
        'is_active',
        'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'states')
