from decimal import Decimal
from rest_framework import serializers
from .models import SiteSettings, ShippingZone


class SiteSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer exposing public storefront configurations and operational policies.
    """
    class Meta:
        model = SiteSettings
        fields = [
            'id',
            'site_name',
            'contact_email',
            'contact_phone',
            'address',
            'maintenance_mode',
            'minimum_order_value',
            'standard_shipping_fee',
            'free_shipping_threshold',
            'cod_charge',
            'is_zone_shipping_enabled',
            'partial_cod_deposit_percentage',
            'updated_at',
        ]
        read_only_fields = fields


class ShippingZoneSerializer(serializers.ModelSerializer):
    """
    Serializer for geographic shipping zones with parsed state coverage lists.
    """
    state_list = serializers.SerializerMethodField()

    class Meta:
        model = ShippingZone
        fields = [
            'id',
            'name',
            'states',
            'state_list',
            'shipping_fee',
            'free_shipping_threshold',
            'cod_charge',
            'is_active',
            'updated_at',
        ]
        read_only_fields = ['id', 'state_list', 'updated_at']

    def get_state_list(self, obj):
        return obj.get_state_list()


class ShippingEstimateRequestSerializer(serializers.Serializer):
    """
    Validates inbound parameters for dynamic shipping and surcharge calculation.
    """
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text="Destination state or province name"
    )
    subtotal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.00'),
        default=Decimal('0.00'),
        help_text="Cart subtotal monetary amount"
    )
    is_cod = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Flag indicating if Cash On Delivery is selected"
    )


class ShippingEstimateResponseSerializer(serializers.Serializer):
    """
    Serializes computed shipping estimates, free shipping thresholds, and order totals.
    """
    state = serializers.CharField()
    matched_zone = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    shipping_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    standard_zone_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_free_shipping = serializers.BooleanField()
    free_shipping_threshold = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount_needed_for_free_shipping = serializers.DecimalField(max_digits=10, decimal_places=2)
    cod_charge = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_cod = serializers.BooleanField()
    partial_cod_deposit_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    deposit_amount_due = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    meets_minimum_order = serializers.BooleanField()
    maintenance_mode = serializers.BooleanField()
