from rest_framework import serializers
from .models import Category


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
        # Relies on prefetch_related('subcategories') to avoid N+1 queries
        children = obj.subcategories.all()
        if children.exists():
            return CategoryTreeSerializer(children, many=True, context=self.context).data
        return []
