from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Category
from .serializers import CategorySerializer, CategoryTreeSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public catalog category viewset.
    Provides flat listings, slug-based lookups, and optimized hierarchical trees.
    """
    queryset = Category.objects.all().select_related('parent')
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return self.queryset.order_by('header_order', 'name')

    @action(detail=False, methods=['get'], url_path='header-menu')
    def header_menu(self, request):
        """
        Returns top-level navigation categories with nested subcategories.
        Optimized with prefetch_related to eliminate N+1 database queries.
        """
        root_categories = Category.objects.filter(
            parent__isnull=True,
            show_in_header=True
        ).prefetch_related(
            'subcategories__subcategories'
        ).order_by('header_order', 'name')

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
        """
        homepage_categories = Category.objects.filter(
            show_on_homepage=True
        ).order_by('homepage_order', 'name')

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
        root_categories = Category.objects.filter(
            parent__isnull=True
        ).prefetch_related(
            'subcategories__subcategories'
        ).order_by('header_order', 'name')

        serializer = CategoryTreeSerializer(
            root_categories,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
