from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ['product', 'variant', 'quantity', 'get_unit_price', 'get_line_total', 'updated_at']
    readonly_fields = ['get_unit_price', 'get_line_total', 'updated_at']

    def get_unit_price(self, obj):
        return f"₹{obj.unit_price:.2f}"
    get_unit_price.short_description = "Unit Price"

    def get_line_total(self, obj):
        return f"₹{obj.line_total:.2f}"
    get_line_total.short_description = "Line Total"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_owner', 'get_total_items', 'get_subtotal', 'abandoned_email_sent', 'updated_at']
    list_filter = ['abandoned_email_sent', 'created_at', 'updated_at']
    search_fields = ['user__email', 'session_key']
    readonly_fields = ['get_subtotal', 'get_total_items', 'created_at', 'updated_at']
    inlines = [CartItemInline]
    actions = ['send_recovery_email_action']

    @admin.action(description="Dispatch recovery email to selected abandoned carts")
    def send_recovery_email_action(self, request, queryset):
        from .tasks import dispatch_single_cart_recovery_email
        dispatched = 0
        for cart in queryset.filter(items__isnull=False, user__isnull=False, abandoned_email_sent=False):
            dispatch_single_cart_recovery_email.delay(cart.id)
            dispatched += 1
        self.message_user(request, f"Queued recovery emails for {dispatched} cart(s).")

    def get_owner(self, obj):
        if obj.user:
            return f"User: {obj.user.email}"
        return f"Guest: {obj.session_key[:12]}..."
    get_owner.short_description = "Cart Owner"

    def get_total_items(self, obj):
        return obj.total_items
    get_total_items.short_description = "Total Items"

    def get_subtotal(self, obj):
        return f"₹{obj.subtotal:.2f}"
    get_subtotal.short_description = "Subtotal"

