from rest_framework import serializers
from .models import Category, Product, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    """
    Flat category serializer with breadcrumbs and parent metadata.
    Used for category listings, filters, and detail views.
    """
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    breadcrumbs = serializers.ReadOnlyField()

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'parent',
            'parent_name',
            'image',
            'show_in_header',
            'show_on_homepage',
            'header_order',
            'homepage_order',
            'breadcrumbs',
            'created_at',
        ]
        read_only_fields = ['slug', 'created_at']


class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Hierarchical category serializer with recursive subcategory nesting.
    Used for storefront mega-menus, navigation bars, and category trees.
    """
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'image',
            'header_order',
            'subcategories',
        ]

    def get_subcategories(self, obj):
        # Materialize from prefetch cache to avoid issuing extra SQL queries.
        # Calling .exists() or .filter() on a prefetched related manager bypasses
        # Django's prefetch cache and triggers an uncached database query.
        children = [
            child for child in obj.subcategories.all()
            if child.show_in_header
        ]
        if children:
            children.sort(key=lambda c: (c.header_order, c.name))
            return CategoryTreeSerializer(children, many=True, context=self.context).data
        return []


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Serializer for child product variants (SKUs).
    Exposes discrete inventory, SKU code, price override, and resolved effective price.
    """
    effective_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            'id',
            'product',
            'name',
            'sku',
            'price_override',
            'effective_price',
            'stock_count',
            'in_stock',
            'image',
        ]
        read_only_fields = ['id', 'effective_price', 'in_stock']


class ProductListSerializer(serializers.ModelSerializer):
    """
    Lightweight catalog serializer for listing grids, category collections,
    and search result cards.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    discount_percentage = serializers.ReadOnlyField()
    is_discounted = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'slug',
            'category',
            'category_name',
            'category_slug',
            'price',
            'compare_price',
            'discount_percentage',
            'is_discounted',
            'short_description',
            'stock_count',
            'in_stock',
            'is_live',
            'is_hero',
            'is_popular',
            'is_combo',
            'created_at',
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive product serializer for Product Detail Pages (PDP).
    Includes nested child variants, category hierarchy breadcrumbs,
    and statutory GST metadata.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    category_breadcrumbs = serializers.ReadOnlyField(source='category.breadcrumbs')
    discount_percentage = serializers.ReadOnlyField()
    is_discounted = serializers.ReadOnlyField()
    variants_list = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'slug',
            'category',
            'category_name',
            'category_slug',
            'category_breadcrumbs',
            'price',
            'compare_price',
            'discount_percentage',
            'is_discounted',
            'short_description',
            'description',
            'stock_count',
            'in_stock',
            'is_live',
            'is_hero',
            'is_popular',
            'is_combo',
            'variant_name',
            'variants',
            'metafields',
            'gst_rate',
            'hsn_code',
            'variants_list',
            'created_at',
            'updated_at',
        ]
