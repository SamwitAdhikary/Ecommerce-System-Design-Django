from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Category


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
