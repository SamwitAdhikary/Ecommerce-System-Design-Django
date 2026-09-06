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
