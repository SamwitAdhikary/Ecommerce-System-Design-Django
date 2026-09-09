from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    CategoryTreeSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public catalog category viewset.
    Provides flat listings, slug-based lookups, and optimized hierarchical trees.
    """
    queryset = Category.objects.all().select_related('parent__parent')
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return self.queryset.order_by('header_order', 'name')

    @action(detail=False, methods=['get'], url_path='header-menu')
    def header_menu(self, request):
        """
        Returns top-level navigation categories with nested subcategories.
        Optimized with prefetch_related across all levels to eliminate N+1 queries.
        """
        root_categories = (
            Category.objects.filter(parent__isnull=True, show_in_header=True)
            .prefetch_related('subcategories__subcategories__subcategories')
            .order_by('header_order', 'name')
        )

        serializer = CategoryTreeSerializer(
            root_categories,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='homepage')
    def homepage(self, request):
        """
        Returns curated category cards for the storefront landing page.
        Optimized with select_related to eliminate N+1 queries during breadcrumb computation.
        """
        homepage_categories = (
            Category.objects.filter(show_on_homepage=True)
            .select_related('parent__parent')
            .order_by('homepage_order', 'name')
        )

        serializer = CategorySerializer(
            homepage_categories,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='tree')
    def tree(self, request):
        """
        Returns the entire catalog category hierarchy as a recursive tree.
        """
        root_categories = (
            Category.objects.filter(parent__isnull=True)
            .prefetch_related('subcategories__subcategories__subcategories')
            .order_by('header_order', 'name')
        )

        serializer = CategoryTreeSerializer(
            root_categories,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public catalog product viewset.
    Provides paginated listings, slug-based lookups, merchandising filters,
    and optimized child variant serialization.
    """
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Product.objects.filter(is_live=True).select_related('category')
        if self.action == 'retrieve':
            qs = qs.prefetch_related('variants_list')

        category_slug = self.request.query_params.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        is_popular = self.request.query_params.get('is_popular')
        if is_popular and is_popular.lower() == 'true':
            qs = qs.filter(is_popular=True)

        is_hero = self.request.query_params.get('is_hero')
        if is_hero and is_hero.lower() == 'true':
            qs = qs.filter(is_hero=True)

        is_combo = self.request.query_params.get('is_combo')
        if is_combo and is_combo.lower() == 'true':
            qs = qs.filter(is_combo=True)

        in_stock_only = self.request.query_params.get('in_stock')
        if in_stock_only and in_stock_only.lower() == 'true':
            qs = qs.filter(in_stock=True)

        ordering = self.request.query_params.get('ordering')
        if ordering in ['price', '-price', 'created_at', '-created_at', 'name']:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by('-created_at')

        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer
