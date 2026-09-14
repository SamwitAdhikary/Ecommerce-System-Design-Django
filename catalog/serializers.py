from rest_framework import serializers
from .models import Category, Product, ProductVariant, ProductImage


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
        children = [
            child for child in obj.subcategories.all()
            if child.show_in_header
        ]
        if children:
            children.sort(key=lambda c: (c.header_order, c.name))
            return CategoryTreeSerializer(children, many=True, context=self.context).data
        return []


class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for multi-image product gallery assets.
    Exposes WebP image URL, descriptive alt text, thumbnail flag, sort order, and variant binding.
    """
    class Meta:
        model = ProductImage
        fields = [
            'id',
            'image',
            'alt_text',
            'is_thumbnail',
            'order',
            'variant',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


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
    thumbnail = serializers.SerializerMethodField()

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
            'thumbnail',
            'short_description',
            'stock_count',
            'in_stock',
            'is_live',
            'is_hero',
            'is_popular',
            'is_combo',
            'created_at',
        ]

    def get_thumbnail(self, obj):
        img = obj.thumbnail_image
        if img and img.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(img.image.url)
            return img.image.url
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive product serializer for Product Detail Pages (PDP).
    Includes nested child variants, gallery images, category breadcrumbs,
    and statutory GST metadata.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    category_breadcrumbs = serializers.ReadOnlyField(source='category.breadcrumbs')
    discount_percentage = serializers.ReadOnlyField()
    is_discounted = serializers.ReadOnlyField()
    thumbnail = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
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
            'thumbnail',
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
            'images',
            'variants_list',
            'created_at',
            'updated_at',
        ]

    def get_thumbnail(self, obj):
        img = obj.thumbnail_image
        if img and img.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(img.image.url)
            return img.image.url
        return None
