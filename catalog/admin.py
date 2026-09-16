from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
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


class SubcategoryInline(TabularInline):
    model = Category
    fk_name = 'parent'
    extra = 1
    fields = ('name', 'slug', 'show_in_header', 'show_on_homepage', 'header_order')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = (
        'name',
        'parent',
        'slug',
        'show_in_header',
        'show_on_homepage',
        'header_order',
        'homepage_order',
    )
    list_filter = ('show_in_header', 'show_on_homepage', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SubcategoryInline]


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'alt_text', 'is_thumbnail', 'order', 'variant')


class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('name', 'sku', 'price_override', 'stock_count', 'image')


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = (
        'name',
        'category',
        'price',
        'compare_price',
        'stock_count',
        'in_stock',
        'is_live',
        'is_hero',
        'is_popular',
        'is_combo',
        'gst_rate',
    )
    list_filter = (
        'is_live',
        'in_stock',
        'is_hero',
        'is_popular',
        'is_combo',
        'category',
        'gst_rate',
    )
    search_fields = ('name', 'slug', 'hsn_code', 'variants_list__sku')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVariantInline]
    fieldsets = (
        ("General Information", {
            'fields': ('name', 'slug', 'category', 'short_description', 'description')
        }),
        ("Pricing & Margins", {
            'fields': ('price', 'compare_price', 'cost_price')
        }),
        ("Inventory & Merchandising", {
            'fields': ('stock_count', 'in_stock', 'is_live', 'is_hero', 'is_popular', 'is_combo')
        }),
        ("Statutory Tax Compliance", {
            'fields': ('gst_rate', 'hsn_code')
        }),
        ("Variant & Metafield Metadata", {
            'fields': ('variant_name', 'variants', 'metafields')
        }),
    )


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    list_display = (
        'name',
        'product',
        'sku',
        'price_override',
        'effective_price',
        'stock_count',
        'in_stock',
    )
    list_filter = ('product__category',)
    search_fields = ('name', 'sku', 'product__name')


@admin.register(ProductImage)
class ProductImageAdmin(ModelAdmin):
    list_display = (
        'id',
        'product',
        'variant',
        'alt_text',
        'is_thumbnail',
        'order',
        'created_at',
    )
    list_filter = ('is_thumbnail', 'product__category')
    search_fields = ('product__name', 'alt_text', 'variant__name')


class ReviewImageInline(TabularInline):
    model = ReviewImage
    extra = 0
    fields = ('image', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = (
        'id',
        'product',
        'user',
        'rating',
        'verified_purchase',
        'is_approved',
        'created_at',
    )
    list_filter = ('rating', 'verified_purchase', 'is_approved', 'created_at')
    search_fields = ('product__name', 'user__email', 'comment')
    actions = ['approve_reviews', 'unapprove_reviews']
    inlines = [ReviewImageInline]

    @admin.action(description="Approve selected customer reviews")
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="Unapprove / hide selected customer reviews")
    def unapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)


@admin.register(Wishlist)
class WishlistAdmin(ModelAdmin):
    list_display = ('id', 'user', 'product_count', 'updated_at')
    search_fields = ('user__email',)
    filter_horizontal = ('products',)

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = "Saved Items"


@admin.register(ActiveVisitor)
class ActiveVisitorAdmin(ModelAdmin):
    list_display = (
        'session_key_preview',
        'ip_address',
        'city',
        'region',
        'country',
        'current_page',
        'action',
        'last_activity',
    )
    list_filter = ('action', 'country', 'current_page')
    search_fields = ('session_key', 'ip_address', 'city', 'region')

    def session_key_preview(self, obj):
        return f"{obj.session_key[:12]}..."
    session_key_preview.short_description = "Session"

