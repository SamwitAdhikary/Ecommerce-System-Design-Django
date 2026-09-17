from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from django.db import transaction
import uuid

from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer
from catalog.models import Product, ProductVariant


class CartViewSet(viewsets.ViewSet):
    """
    Storefront shopping cart endpoint supporting both authenticated users and anonymous guest visitors.
    Provides atomic item addition, quantity updates, removal, flushes, and login state merges.
    """
    permission_classes = [permissions.AllowAny]

    def _get_or_create_cart(self, request) -> Cart:
        """
        Resolves or instantiates the active Cart entity based on authentication state
        or guest session identifier.
        """
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(
                user=request.user,
                defaults={'session_key': None}
            )
            return cart

        session_key = (
            request.data.get('session_key')
            or request.headers.get('X-Session-Key')
            or request.query_params.get('session_key')
        )

        if not session_key:
            if not request.session.session_key:
                request.session.save()
            session_key = request.session.session_key or f"guest-{uuid.uuid4().hex[:16]}"

        cart, _ = Cart.objects.get_or_create(
            session_key=session_key,
            user=None
        )
        return cart

    def list(self, request):
        """
        GET /api/orders/cart/
        Retrieves the active cart for the requesting user or guest session with live totals.
        """
        cart = self._get_or_create_cart(request)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='add_item')
    def add_item(self, request):
        """
        POST /api/orders/cart/add_item/
        Adds a product and optional variant to the cart or increments existing quantity.
        Caps added quantity at available catalog inventory.
        """
        cart = self._get_or_create_cart(request)
        product_id = request.data.get('product_id') or request.data.get('product')
        variant_id = request.data.get('variant_id') or request.data.get('variant')

        if not product_id:
            raise ValidationError({"product_id": "Product ID is required."})

        try:
            quantity = int(request.data.get('quantity', 1))
            if quantity < 1:
                quantity = 1
        except (ValueError, TypeError):
            quantity = 1

        try:
            product = Product.objects.get(pk=product_id)
        except (Product.DoesNotExist, ValueError):
            raise NotFound({"product": "Product not found."})

        variant = None
        if variant_id:
            try:
                # Support variant lookup by integer ID or SKU name string
                if isinstance(variant_id, int) or str(variant_id).isdigit():
                    variant = ProductVariant.objects.get(pk=int(variant_id), product=product)
                else:
                    variant = ProductVariant.objects.get(name=str(variant_id), product=product)
            except ProductVariant.DoesNotExist:
                raise NotFound({"variant": "Product variant not found for this product."})

        # Calculate effective available inventory
        effective_stock = variant.stock_count if variant else product.stock_count

        if not product.is_live or effective_stock <= 0:
            return Response(
                {"error": "This item is currently out of stock or unavailable."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            cart_item = CartItem.objects.filter(
                cart=cart,
                product=product,
                variant=variant
            ).first()

            if cart_item:
                new_quantity = min(cart_item.quantity + quantity, effective_stock)
                cart_item.quantity = max(1, new_quantity)
                cart_item.save(update_fields=['quantity', 'updated_at'])
            else:
                clamped_quantity = min(quantity, effective_stock)
                cart_item = CartItem.objects.create(
                    cart=cart,
                    product=product,
                    variant=variant,
                    quantity=max(1, clamped_quantity)
                )

        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post', 'patch'], url_path='update_item')
    def update_item(self, request):
        """
        POST/PATCH /api/orders/cart/update_item/
        Updates quantity for a specific line item. If quantity <= 0, deletes the line item.
        """
        cart = self._get_or_create_cart(request)
        item_id = request.data.get('item_id') or request.data.get('id')

        if not item_id:
            raise ValidationError({"item_id": "Item ID is required."})

        try:
            quantity = int(request.data.get('quantity', 1))
        except (ValueError, TypeError):
            raise ValidationError({"quantity": "A valid integer quantity is required."})

        try:
            cart_item = CartItem.objects.get(pk=item_id, cart=cart)
        except CartItem.DoesNotExist:
            raise NotFound({"detail": "Cart item not found in active cart."})

        with transaction.atomic():
            if quantity <= 0:
                cart_item.delete()
            else:
                effective_stock = cart_item.effective_stock
                cart_item.quantity = min(quantity, effective_stock)
                cart_item.save(update_fields=['quantity', 'updated_at'])

        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post', 'delete'], url_path='remove_item')
    def remove_item(self, request):
        """
        POST/DELETE /api/orders/cart/remove_item/
        Deletes a specific line item from the active cart.
        """
        cart = self._get_or_create_cart(request)
        item_id = (
            request.data.get('item_id')
            or request.data.get('id')
            or request.query_params.get('item_id')
        )

        if not item_id:
            raise ValidationError({"item_id": "Item ID is required."})

        try:
            cart_item = CartItem.objects.get(pk=item_id, cart=cart)
            cart_item.delete()
        except CartItem.DoesNotExist:
            raise NotFound({"detail": "Cart item not found in active cart."})

        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post', 'delete'], url_path='clear')
    def clear(self, request):
        """
        POST/DELETE /api/orders/cart/clear/
        Removes all items from the active cart.
        """
        cart = self._get_or_create_cart(request)
        cart.items.all().delete()
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='merge')
    def merge(self, request):
        """
        POST /api/orders/cart/merge/
        Merges an anonymous guest session cart into the authenticated user's cart upon login.
        """
        guest_session_key = (
            request.data.get('session_key')
            or request.headers.get('X-Session-Key')
        )

        if not guest_session_key:
            cart = self._get_or_create_cart(request)
            serializer = CartSerializer(cart, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        guest_cart = Cart.objects.filter(session_key=guest_session_key, user=None).first()
        if guest_cart and not guest_cart.is_empty:
            user_cart = guest_cart.merge_with_user(request.user)
        else:
            user_cart = self._get_or_create_cart(request)

        serializer = CartSerializer(user_cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
