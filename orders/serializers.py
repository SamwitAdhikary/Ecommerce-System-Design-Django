from rest_framework import serializers
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer for individual cart line items with live pricing,
    variant descriptions, stock availability, and image resolution.
    """
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    variant_name = serializers.SerializerMethodField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    compare_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    effective_stock = serializers.IntegerField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id',
            'product',
            'product_name',
            'product_slug',
            'variant',
            'variant_name',
            'quantity',
            'unit_price',
            'compare_price',
            'line_total',
            'effective_stock',
            'is_available',
            'image_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'product_name',
            'product_slug',
            'variant_name',
            'unit_price',
            'compare_price',
            'line_total',
            'effective_stock',
            'is_available',
            'image_url',
            'created_at',
            'updated_at',
        ]

    def get_variant_name(self, obj) -> str | None:
        if obj.variant:
            return obj.variant.name
        return None

    def get_image_url(self, obj) -> str | None:
        url = obj.image_url
        if url:
            request = self.context.get('request')
            if request and not url.startswith(('http://', 'https://')):
                return request.build_absolute_uri(url)
            return url
        return None


class CartSerializer(serializers.ModelSerializer):
    """
    Comprehensive representation of a shopping cart with nested line items,
    total item counts, and calculated live subtotal.
    """
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_empty = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cart
        fields = [
            'id',
            'session_key',
            'items',
            'total_items',
            'subtotal',
            'is_empty',
            'abandoned_email_sent',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'session_key',
            'items',
            'total_items',
            'subtotal',
            'is_empty',
            'abandoned_email_sent',
            'created_at',
            'updated_at',
        ]
