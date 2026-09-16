from rest_framework import serializers
from .models import (
    Category,
    Product,
    ProductVariant,
    ProductImage,
    Review,
    ReviewImage,
    Wishlist,
    ActiveVisitor,
)


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


class ReviewImageSerializer(serializers.ModelSerializer):
    """
    Serializer for customer review photo attachments.
    """
    class Meta:
        model = ReviewImage
        fields = ['id', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']


class ReviewSerializer(serializers.ModelSerializer):
    """
    Public and customer review serializer exposing author name, star rating,
    detailed comment, verified purchase badge, and attached customer photos.
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    images = ReviewImageSerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields = [
            'id',
            'product',
            'product_name',
            'product_slug',
            'user',
            'user_email',
            'user_name',
            'rating',
            'comment',
            'verified_purchase',
            'is_approved',
            'images',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'verified_purchase', 'is_approved', 'created_at', 'updated_at']

    def get_user_name(self, obj) -> str:
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name if name else obj.user.email.split('@')[0]


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
    rating = serializers.FloatField(source='average_rating', read_only=True)
    review_count = serializers.IntegerField(read_only=True)

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
            'rating',
            'review_count',
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
    statutory GST metadata, customer reviews, and aggregated star ratings.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    category_breadcrumbs = serializers.ReadOnlyField(source='category.breadcrumbs')
    discount_percentage = serializers.ReadOnlyField()
    is_discounted = serializers.ReadOnlyField()
    thumbnail = serializers.SerializerMethodField()
    rating = serializers.FloatField(source='average_rating', read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    rating_breakdown = serializers.DictField(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants_list = ProductVariantSerializer(many=True, read_only=True)
    reviews = serializers.SerializerMethodField()

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
            'rating',
            'review_count',
            'rating_breakdown',
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
            'reviews',
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

    def get_reviews(self, obj):
        if hasattr(obj, '_prefetched_objects_cache') and 'reviews' in obj._prefetched_objects_cache:
            approved = [r for r in obj.reviews.all() if r.is_approved]
        else:
            approved = obj.reviews.filter(is_approved=True).select_related('user').prefetch_related('images')
        return ReviewSerializer(approved, many=True, context=self.context).data


class WishlistSerializer(serializers.ModelSerializer):
    """
    Customer wishlist serializer with nested product cards and total item count.
    """
    products = ProductListSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = ['id', 'products', 'total_items', 'updated_at']
        read_only_fields = ['id', 'total_items', 'updated_at']

    def get_total_items(self, obj) -> int:
        return obj.products.count()


class ActiveVisitorSerializer(serializers.ModelSerializer):
    """
    Storefront active visitor telemetry serializer.
    """
    class Meta:
        model = ActiveVisitor
        fields = [
            'id',
            'session_key',
            'ip_address',
            'city',
            'region',
            'country',
            'latitude',
            'longitude',
            'current_page',
            'action',
            'last_activity',
        ]
        read_only_fields = ['id', 'last_activity']

