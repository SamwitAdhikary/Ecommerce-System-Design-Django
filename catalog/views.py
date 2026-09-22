from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.apps import apps
from .models import (
    Category,
    Product,
    Review,
    ReviewImage,
    Wishlist,
    ActiveVisitor,
)
from .serializers import (
    CategorySerializer,
    CategoryTreeSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ReviewSerializer,
    WishlistSerializer,
    ActiveVisitorSerializer,
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
    and optimized child variant & review serialization.
    """
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Product.objects.filter(is_live=True).select_related('category').prefetch_related('images', 'reviews')
        if self.action == 'retrieve':
            qs = qs.prefetch_related(
                'variants_list',
                'images',
                'reviews__user',
                'reviews__images'
            )

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


def check_verified_purchase(user, product) -> bool:
    """
    Evaluates whether the user has purchased and received the physical product.
    Uses dynamic model resolution (apps.get_model) to preserve modular decoupling between apps.
    """
    if not user or not user.is_authenticated:
        return False

    try:
        Order = apps.get_model('orders', 'Order')
        return Order.objects.filter(
            user=user,
            items__product=product,
            status='DELIVERED'
        ).exists()
    except (LookupError, AttributeError):
        return False


class ReviewViewSet(viewsets.ModelViewSet):
    """
    Storefront review management viewset.
    Allows authenticated customers to write reviews, upload unboxing photos,
    and verifies delivered purchase history.
    """
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Review.objects.select_related('user', 'product').prefetch_related('images')
        product_id = self.request.query_params.get('product')
        product_slug = self.request.query_params.get('product_slug')

        if product_id:
            qs = qs.filter(product_id=product_id, is_approved=True)
        elif product_slug:
            qs = qs.filter(product__slug=product_slug, is_approved=True)
        elif self.request.query_params.get('my_reviews') == 'true' and self.request.user.is_authenticated:
            qs = qs.filter(user=self.request.user)
        elif not self.request.user.is_staff:
            qs = qs.filter(is_approved=True)

        return qs.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product')
        product_slug = request.data.get('product_slug')

        if not product_id and not product_slug:
            raise ValidationError({"product": "Product ID or slug is required."})

        try:
            if product_id:
                product = Product.objects.get(pk=product_id)
            else:
                product = Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            raise ValidationError({"product": "Product not found."})

        user = request.user
        if not user.is_authenticated:
            raise PermissionDenied("Authentication required to submit a review.")

        # 1. Prevent duplicate reviews by the same user
        if Review.objects.filter(product=product, user=user).exists():
            raise ValidationError({"detail": "You have already reviewed this product."})

        # 2. Rating validation
        try:
            rating = int(request.data.get('rating', 0))
            if rating < 1 or rating > 5:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError({"rating": "Star rating must be an integer between 1 and 5."})

        comment = request.data.get('comment', '').strip()

        # 3. Check for verified purchase against delivered orders
        is_verified = check_verified_purchase(user, product)

        # 4. Ingest review
        review = Review.objects.create(
            product=product,
            user=user,
            rating=rating,
            comment=comment,
            verified_purchase=is_verified,
            is_approved=True  # Default auto-approved
        )

        # 5. Handle customer photo uploads
        images = request.FILES.getlist('images')
        for img in images:
            ReviewImage.objects.create(review=review, image=img)

        serializer = self.get_serializer(review)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated], url_path='eligibility')
    def eligibility(self, request):
        """
        Evaluates whether the authenticated user can review a specific product.
        Returns can_review boolean, already_reviewed flag, and verified_purchase flag.
        """
        product_id = request.query_params.get('product_id')
        product_slug = request.query_params.get('product_slug')

        if not product_id and not product_slug:
            return Response({"error": "product_id or product_slug query parameter is required."}, status=400)

        try:
            if product_id:
                product = Product.objects.get(pk=product_id)
            else:
                product = Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=404)

        user = request.user
        already_reviewed = Review.objects.filter(product=product, user=user).exists()
        is_verified = check_verified_purchase(user, product)

        return Response({
            "product_id": product.id,
            "product_slug": product.slug,
            "can_review": not already_reviewed,
            "already_reviewed": already_reviewed,
            "is_verified": is_verified,
        })

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You can only edit your own reviews.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You can only delete your own reviews.")
        instance.delete()


class WishlistViewSet(viewsets.ModelViewSet):
    """
    Authenticated customer wishlist viewset.
    Provides wishlist retrieval and atomic product toggling.
    """
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).prefetch_related(
            'products__category',
            'products__images'
        )

    def get_object(self):
        wishlist, _ = Wishlist.objects.get_or_create(user=self.request.user)
        return wishlist

    def list(self, request, *args, **kwargs):
        wishlist = self.get_object()
        serializer = self.get_serializer(wishlist)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle(self, request):
        """
        Atomically adds or removes a product from the user's wishlist.
        """
        product_id = request.data.get('product_id')
        product_slug = request.data.get('product_slug')

        if not product_id and not product_slug:
            return Response({"error": "product_id or product_slug is required."}, status=400)

        try:
            if product_id:
                product = Product.objects.get(pk=product_id)
            else:
                product = Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=404)

        wishlist = self.get_object()
        is_added, total_items = wishlist.toggle(product)

        return Response({
            "status": "added" if is_added else "removed",
            "is_added": is_added,
            "total_items": total_items,
            "product_id": product.id,
            "product_name": product.name,
            "product_slug": product.slug,
        })

    @action(detail=False, methods=['delete'], url_path='clear')
    def clear(self, request):
        """
        Removes all saved products from the user's wishlist.
        """
        wishlist = self.get_object()
        wishlist.products.clear()
        return Response({"status": "cleared", "total_items": 0})


class ActiveVisitorViewSet(viewsets.ViewSet):
    """
    Storefront active visitor telemetry viewset.
    Receives frontend heartbeats and returns live presence metrics.
    Exposes dedicated heartbeat and stats actions without full ModelViewSet CRUD surface.
    """
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'], url_path='heartbeat')
    def heartbeat(self, request):
        """
        Ingests a client presence heartbeat and updates/creates the visitor record.
        Real-time counts query the indexed active TTL window (15 mins), while physical
        cleanup is offloaded to the 'prune_active_visitors' management command.
        """
        from django.utils import timezone
        import datetime
        import uuid

        session_key = request.data.get('session_key')
        if not session_key:
            if not request.session.session_key:
                request.session.save()
            session_key = request.session.session_key or f"anon-{uuid.uuid4().hex[:12]}"

        current_page = request.data.get('current_page', 'Shop')
        action_name = request.data.get('action', 'viewing')

        # Extract client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')

        visitor, _ = ActiveVisitor.objects.update_or_create(
            session_key=session_key,
            defaults={
                'ip_address': ip_address,
                'current_page': current_page,
                'action': action_name,
                'city': request.data.get('city', 'Unknown'),
                'region': request.data.get('region', 'Unknown'),
                'country': request.data.get('country', 'India'),
            }
        )

        # Fast query over active window without hammering database with synchronous DELETEs
        cutoff = timezone.now() - datetime.timedelta(minutes=15)
        total_active = ActiveVisitor.objects.filter(last_activity__gte=cutoff).count()
        page_active = ActiveVisitor.objects.filter(current_page=current_page, last_activity__gte=cutoff).count()

        return Response({
            "status": "ok",
            "session_key": visitor.session_key,
            "active_visitors": total_active,
            "page_visitors": page_active,
        })

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """
        Returns live storefront presence statistics.
        """
        from django.utils import timezone
        import datetime
        cutoff = timezone.now() - datetime.timedelta(minutes=15)
        active_qs = ActiveVisitor.objects.filter(last_activity__gte=cutoff)
        total_active = active_qs.count()
        return Response({
            "total_active_visitors": total_active,
            "by_action": list(
                active_qs.values('action')
            ),
        })


