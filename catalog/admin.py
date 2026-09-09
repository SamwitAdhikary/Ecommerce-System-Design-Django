from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Category, Product, ProductVariant


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
    inlines = [ProductVariantInline]
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
