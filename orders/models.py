from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal


class Cart(models.Model):
    """
    Persistent shopping cart entity supporting both authenticated customers and guest visitors.
    Acts as a transient transaction buffer prior to checkout and order snapshotting.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='cart',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Authenticated customer owning this cart. Null for guest sessions."
    )
    session_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Anonymous session identifier for unauthenticated guest visitors."
    )
    abandoned_email_sent = models.BooleanField(
        default=False,
        help_text="Indicates whether an abandoned cart recovery notification has been dispatched."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart"
        verbose_name_plural = "Carts"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['session_key'], name='idx_cart_session_key'),
            models.Index(fields=['user', '-updated_at'], name='idx_cart_user_updated'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['session_key'],
                condition=models.Q(session_key__isnull=False),
                name='unique_session_cart'
            ),
            models.CheckConstraint(
                condition=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name='cart_has_user_or_session'
            ),
        ]

    def __str__(self):
        if self.user:
            return f"Cart (User: {self.user.email})"
        return f"Cart (Session: {self.session_key})"

    @property
    def total_items(self) -> int:
        """
        Computes the total sum of all item quantities currently in the cart.
        """
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self) -> Decimal:
        """
        Calculates the live subtotal across all cart items.
        Dynamically reflects real-time catalog prices without relying on stale snapshots.
        """
        return sum((item.line_total for item in self.items.all()), Decimal('0.00'))

    @property
    def is_empty(self) -> bool:
        return not self.items.exists()

    def merge_with_user(self, user):
        """
        Atomically merges this anonymous/guest cart into the authenticated user's cart upon login.
        If the user already owns an active cart, line items are combined (capped by live stock).
        The transient guest cart record is subsequently deleted.
        """
        if not user or not user.is_authenticated:
            return self

        from django.db import transaction

        with transaction.atomic():
            user_cart, _ = Cart.objects.select_for_update().get_or_create(
                user=user,
                defaults={'session_key': None}
            )

            if self.pk == user_cart.pk:
                return user_cart

            for guest_item in self.items.select_related('product', 'variant').all():
                user_item = user_cart.items.filter(
                    product=guest_item.product,
                    variant=guest_item.variant
                ).first()

                effective_stock = guest_item.effective_stock

                if user_item:
                    new_quantity = min(user_item.quantity + guest_item.quantity, effective_stock)
                    user_item.quantity = max(1, new_quantity)
                    user_item.save(update_fields=['quantity', 'updated_at'])
                else:
                    clamped_quantity = min(guest_item.quantity, effective_stock)
                    CartItem.objects.create(
                        cart=user_cart,
                        product=guest_item.product,
                        variant=guest_item.variant,
                        quantity=max(1, clamped_quantity)
                    )

            self.delete()
            return user_cart


class CartItem(models.Model):
    """
    Individual line item in a customer shopping cart.
    Maps a parent Cart to a catalog Product and an optional SKU ProductVariant.
    """
    cart = models.ForeignKey(
        Cart,
        related_name='items',
        on_delete=models.CASCADE,
        help_text="Parent cart container."
    )
    product = models.ForeignKey(
        'catalog.Product',
        related_name='cart_items',
        on_delete=models.CASCADE,
        help_text="Referenced catalog product."
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        related_name='cart_items',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Specific child SKU variant selection, if applicable."
    )
    quantity = models.PositiveIntegerField(
        "Quantity",
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Number of units added to cart (must be >= 1)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        ordering = ['id']
        indexes = [
            models.Index(fields=['cart', 'product'], name='idx_cartitem_cart_prod'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name='cart_item_quantity_gte_1'
            ),
            models.UniqueConstraint(
                fields=['cart', 'product', 'variant'],
                condition=models.Q(variant__isnull=False),
                name='unique_cart_product_variant'
            ),
            models.UniqueConstraint(
                fields=['cart', 'product'],
                condition=models.Q(variant__isnull=True),
                name='unique_cart_product_no_variant'
            ),
        ]

    def __str__(self):
        variant_label = f" ({self.variant.name})" if self.variant else ""
        return f"{self.quantity}x {self.product.name}{variant_label}"

    @property
    def unit_price(self) -> Decimal:
        """
        Resolves the live unit selling price.
        If a child variant defines price_override, that takes precedence over the base product price.
        """
        if self.variant and self.variant.price_override is not None:
            return self.variant.price_override
        return self.product.price

    @property
    def compare_price(self):
        """
        Returns the original strike-through price (MRP) for discount representation.
        """
        return self.product.compare_price

    @property
    def line_total(self) -> Decimal:
        """
        Computes the total line price (unit_price * quantity).
        """
        return self.unit_price * self.quantity

    @property
    def effective_stock(self) -> int:
        """
        Returns available inventory units for the selected variant or parent product.
        """
        if self.variant:
            return self.variant.stock_count
        return self.product.stock_count

    @property
    def is_available(self) -> bool:
        """
        Returns True if the product is live on storefront and stock covers the requested quantity.
        """
        return bool(self.product.is_live and self.effective_stock >= self.quantity)

    @property
    def image_url(self) -> str | None:
        """
        Resolves the most specific image for this line item (variant image first, thumbnail fallback).
        """
        if self.variant and self.variant.image:
            return self.variant.image.url
        thumb = self.product.thumbnail_image
        if thumb and thumb.image:
            return thumb.image.url
        return None


@receiver(post_save, sender=CartItem)
@receiver(post_delete, sender=CartItem)
def reset_cart_abandoned_status(sender, instance, **kwargs):
    """
    When cart contents are modified, reset the abandoned_email_sent flag
    so recovery automations can re-trigger if the shopper abandons the updated cart.
    """
    try:
        cart = instance.cart
        if cart.abandoned_email_sent:
            cart.abandoned_email_sent = False
            cart.save(update_fields=['abandoned_email_sent', 'updated_at'])
    except Exception:
        pass
