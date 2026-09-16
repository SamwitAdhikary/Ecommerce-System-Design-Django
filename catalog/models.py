from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from core.image_optimizer import compress_image


class Category(models.Model):
    """
    Hierarchical catalog taxonomy model using an Adjacency List pattern.
    Supports multi-level subcategories, automated unique slug generation,
    WebP image optimization, and storefront presentation ordering.
    """
    name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Human-readable category name."
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="URL-friendly unique identifier."
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='subcategories',
        on_delete=models.CASCADE,
        help_text="Parent category. If null, this is a top-level root department."
    )
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        help_text="Category banner or card thumbnail."
    )
    show_in_header = models.BooleanField(
        "Show in Header Menu",
        default=False,
        db_index=True,
        help_text="Display in top navigation bar dropdown menus."
    )
    show_on_homepage = models.BooleanField(
        "Show on Homepage",
        default=True,
        db_index=True,
        help_text="Display in storefront landing page category grid."
    )
    header_order = models.PositiveIntegerField(
        "Header Sort Order",
        default=0,
        help_text="Ascending sort order for header navigation menu."
    )
    homepage_order = models.PositiveIntegerField(
        "Homepage Sort Order",
        default=0,
        help_text="Ascending sort order for homepage category grid."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['header_order', 'name']
        indexes = [
            models.Index(fields=['parent', 'header_order'], name='idx_category_parent_order'),
            models.Index(fields=['show_in_header', 'header_order'], name='idx_category_header_menu'),
            models.Index(fields=['show_on_homepage', 'homepage_order'], name='idx_category_homepage'),
        ]

    def __str__(self):
        ancestors = [c.name for c in self.get_ancestors()]
        return " > ".join(ancestors) if ancestors else self.name

    def clean(self):
        """
        Validates that a category cannot be its own parent or create circular loops.
        """
        super().clean()
        if self.pk and self.parent_id:
            if self.pk == self.parent_id:
                raise ValidationError({'parent': "A category cannot be its own parent."})

            # Check for circular ancestry loops
            curr = self.parent
            visited = {self.pk}
            while curr is not None:
                if curr.pk in visited:
                    raise ValidationError({'parent': "Circular category hierarchy detected."})
                visited.add(curr.pk)
                curr = curr.parent

    def _generate_unique_slug(self) -> str:
        """
        Generates a URL-friendly slug from the category name.
        Appends a sequential integer suffix in the event of collisions.
        """
        base_slug = slugify(self.name)
        if not base_slug:
            base_slug = "category"

        slug = base_slug
        counter = 1
        qs = Category.objects.all()
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        while qs.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def get_ancestors(self) -> list['Category']:
        """
        Traverses upward to return the root-to-node ancestral hierarchy list.
        """
        ancestors = []
        curr = self
        while curr is not None:
            ancestors.append(curr)
            curr = curr.parent
        ancestors.reverse()
        return ancestors

    @property
    def breadcrumbs(self) -> list[dict]:
        """
        Returns a list of dictionary breadcrumbs suitable for storefront navigation.
        """
        return [{'name': c.name, 'slug': c.slug} for c in self.get_ancestors()]

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.slug:
            self.slug = self._generate_unique_slug()
        compress_image(self.image, max_width=800)
        super().save(*args, **kwargs)


class Product(models.Model):
    """
    Canonical catalog parent product entity.
    Manages catalog discovery, SEO routing, merchandising flags,
    statutory GST taxation metadata, and base/compare pricing.
    """
    GST_RATE_CHOICES = (
        (Decimal('0.00'), '0% (Exempt Essentials & Unprocessed Goods)'),
        (Decimal('3.00'), '3% (Gold, Silver & Precious Jewelry)'),
        (Decimal('5.00'), '5% (Apparel, Footwear & Everyday Essentials)'),
        (Decimal('18.00'), '18% (Standard Consumer Goods, Electronics & Services)'),
        (Decimal('40.00'), '40% (Luxury, Premium Demerit & Sin Goods)'),
    )

    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Product title displayed across catalog and product pages."
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="URL-friendly unique product slug."
    )
    category = models.ForeignKey(
        Category,
        related_name='products',
        on_delete=models.PROTECT,
        help_text="Primary category taxonomy node. Protected against accidental deletion."
    )
    price = models.DecimalField(
        "Base Price (₹)",
        max_digits=10,
        decimal_places=2,
        help_text="Base catalog selling price or starting variant price."
    )
    compare_price = models.DecimalField(
        "Compare-at / MRP (₹)",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Original strike-through Maximum Retail Price (MRP) for discount calculation."
    )
    cost_price = models.DecimalField(
        "Cost Price (₹)",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Procurement or manufacturing unit cost for gross profit margin analysis."
    )
    short_description = models.CharField(
        max_length=500,
        blank=True,
        help_text="Concise summary snippet for catalog cards and search previews."
    )
    description = models.TextField(
        "Long Description",
        blank=True,
        help_text="Detailed HTML or Markdown product description."
    )
    stock_count = models.PositiveIntegerField(
        "Stock Count",
        default=0,
        help_text="Available inventory units (managed directly or synchronized with child variants in Chapter 13)."
    )
    in_stock = models.BooleanField(
        "In Stock",
        default=True,
        db_index=True,
        help_text="Instant boolean availability flag."
    )
    is_live = models.BooleanField(
        "Is Live on Storefront",
        default=True,
        db_index=True,
        help_text="Master visibility toggle for storefront catalog listing."
    )
    is_hero = models.BooleanField(
        "Hero Product",
        default=False,
        db_index=True,
        help_text="Spotlight featured banner product on the storefront homepage."
    )
    is_popular = models.BooleanField(
        "Popular Right Now",
        default=False,
        db_index=True,
        help_text="Highlight in recommendation carousels and slide-out cart drawers."
    )
    is_combo = models.BooleanField(
        "Combo Deal / Bundle",
        default=False,
        db_index=True,
        help_text="Designates a multi-item combo or bundled gift set."
    )
    variant_name = models.CharField(
        "Variant Dimension Label",
        max_length=50,
        blank=True,
        null=True,
        help_text="Label for primary variant dimension (e.g., 'Size', 'Color', 'Bundle Pack')."
    )
    variants = models.JSONField(
        "Variant Attribute Schema",
        default=list,
        blank=True,
        help_text="JSON list of variant attribute options (e.g., [{'name': 'Size', 'options': ['S', 'M', 'L']}])."
    )
    metafields = models.JSONField(
        "Custom Metafields",
        default=dict,
        blank=True,
        help_text="Flexible key-value pairs for specifications (fabric, care, origin, warranty)."
    )
    gst_rate = models.DecimalField(
        "GST Slab Rate (%)",
        max_digits=5,
        decimal_places=2,
        choices=GST_RATE_CHOICES,
        default=Decimal('5.00'),
        help_text="Applicable statutory Goods and Services Tax (GST) bracket."
    )
    hsn_code = models.CharField(
        "HSN / SAC Code",
        max_length=20,
        blank=True,
        null=True,
        help_text="Harmonized System of Nomenclature code (e.g., '62052000' for men's cotton shirts) for statutory invoice compliance."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_live', 'category'], name='idx_product_live_category'),
            models.Index(fields=['is_live', 'is_popular'], name='idx_product_live_popular'),
            models.Index(fields=['is_live', 'is_hero'], name='idx_product_live_hero'),
            models.Index(fields=['is_live', 'price'], name='idx_product_live_price'),
        ]

    def __str__(self):
        return self.name

    def _generate_unique_slug(self) -> str:
        base_slug = slugify(self.name)
        if not base_slug:
            base_slug = "product"

        slug = base_slug
        counter = 1
        qs = Product.objects.all()
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        while qs.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    @property
    def discount_percentage(self) -> int:
        """
        Calculates the integer percentage savings compared to compare_price (MRP).
        Returns 0 if no valid compare_price exists or if price >= compare_price.
        """
        if self.compare_price and self.compare_price > self.price:
            savings = (self.compare_price - self.price) / self.compare_price * Decimal('100')
            return int(round(savings))
        return 0

    @property
    def is_discounted(self) -> bool:
        return self.discount_percentage > 0

    def sync_with_variants(self):
        """
        Synchronizes parent stock count, in-stock availability, and starting price
        from related child variants.
        Called automatically on ProductVariant post_save and post_delete signals.
        """
        variants = list(self.variants_list.all())
        if variants:
            # 1. Total Aggregated Stock: Sum of all child SKU inventory counts
            self.stock_count = sum(v.stock_count for v in variants)

            # 2. Starting Price ("Starting at ₹X"): Minimum selling price among child variants
            override_prices = [v.price_override for v in variants if v.price_override is not None]
            if any(v.price_override is None for v in variants):
                self.price = min(override_prices + [self.price])
            elif override_prices:
                self.price = min(override_prices)

            # 3. Availability flag
            self.in_stock = (self.stock_count > 0)

            # Persist atomically with update_fields to avoid race conditions with other fields
            self.save(update_fields=['stock_count', 'in_stock', 'price', 'updated_at'])
        else:
            # When all child variants have been deleted, reset aggregates
            self.stock_count = 0
            self.in_stock = False
            self.save(update_fields=['stock_count', 'in_stock', 'updated_at'])

    @property
    def thumbnail_image(self):
        """
        Returns the primary thumbnail image for the product.
        Falls back to the first image ordered by `order, id` if no image
        is explicitly marked with `is_thumbnail=True`.
        """
        if hasattr(self, '_prefetched_objects_cache') and 'images' in self._prefetched_objects_cache:
            images = list(self.images.all())
            for img in images:
                if img.is_thumbnail:
                    return img
            return images[0] if images else None

        thumbnail = self.images.filter(is_thumbnail=True).first()
        if thumbnail:
            return thumbnail
        return self.images.first()

    @property
    def average_rating(self) -> float:
        """
        Calculates the arithmetic mean of approved customer ratings for this product.
        Returns 0.0 if no approved reviews exist.
        Checks in-memory prefetched cache first to eliminate N+1 queries.
        """
        if hasattr(self, '_prefetched_objects_cache') and 'reviews' in self._prefetched_objects_cache:
            approved = [r.rating for r in self.reviews.all() if r.is_approved]
            return round(sum(approved) / len(approved), 1) if approved else 0.0

        from django.db.models import Avg
        avg = self.reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg']
        return round(float(avg), 1) if avg is not None else 0.0

    @property
    def review_count(self) -> int:
        """
        Returns the total count of approved reviews for this product.
        Checks in-memory prefetched cache first to eliminate N+1 queries.
        """
        if hasattr(self, '_prefetched_objects_cache') and 'reviews' in self._prefetched_objects_cache:
            return sum(1 for r in self.reviews.all() if r.is_approved)
        return self.reviews.filter(is_approved=True).count()

    @property
    def rating_breakdown(self) -> dict:
        """
        Returns a distribution dictionary with counts and percentages for each star rating (1 to 5).
        """
        if hasattr(self, '_prefetched_objects_cache') and 'reviews' in self._prefetched_objects_cache:
            approved = [r.rating for r in self.reviews.all() if r.is_approved]
        else:
            approved = list(self.reviews.filter(is_approved=True).values_list('rating', flat=True))

        total = len(approved)
        breakdown = {}
        for star in range(5, 0, -1):
            count = approved.count(star)
            pct = round((count / total * 100), 1) if total > 0 else 0.0
            breakdown[str(star)] = {'count': count, 'percentage': pct}
        return breakdown

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        self.in_stock = (self.stock_count > 0)
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    """
    Discrete inventory and SKU child entity for a parent product.
    Represents specific size/color/pack permutations with independent
    stock keeping, price overrides, and SKU identifiers.
    """
    product = models.ForeignKey(
        Product,
        related_name='variants_list',
        on_delete=models.CASCADE,
        help_text="Parent product owning this variant."
    )
    name = models.CharField(
        "Variant Name",
        max_length=255,
        help_text="Variant label (e.g., 'Red / XL', '128GB / Midnight Black', 'Pack of 3')."
    )
    price_override = models.DecimalField(
        "Price Override (₹)",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Optional variant-specific selling price. If omitted, inherits parent price."
    )
    stock_count = models.PositiveIntegerField(
        "SKU Stock Count",
        default=0,
        help_text="Current available inventory for this discrete SKU."
    )
    sku = models.CharField(
        "Stock Keeping Unit (SKU)",
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        help_text="Unique inventory tracking code across the entire warehouse."
    )
    image = models.ImageField(
        upload_to='variants/',
        blank=True,
        null=True,
        help_text="Optional variant-specific product photo."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Variant"
        verbose_name_plural = "Product Variants"
        ordering = ['id']
        indexes = [
            models.Index(fields=['product', 'stock_count'], name='idx_variant_prod_stock'),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def effective_price(self) -> Decimal:
        """
        Returns the variant's price override if defined; otherwise falls back to parent price.
        """
        if self.price_override is not None:
            return self.price_override
        return self.product.price

    @property
    def in_stock(self) -> bool:
        return self.stock_count > 0

    def save(self, *args, **kwargs):
        compress_image(self.image, max_width=800)
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    """
    Multi-image gallery asset for a parent product.
    Supports variant-specific photo mapping, drag-and-drop sort ordering,
    explicit primary thumbnail flags, and automated WebP compression.
    """
    product = models.ForeignKey(
        Product,
        related_name='images',
        on_delete=models.CASCADE,
        help_text="Parent product owning this gallery image."
    )
    variant = models.ForeignKey(
        ProductVariant,
        null=True,
        blank=True,
        related_name='variant_images',
        on_delete=models.SET_NULL,
        help_text="Optional variant mapping (e.g., specific colorway photo)."
    )
    image = models.ImageField(
        upload_to='products/',
        help_text="Product photograph (automatically compressed to WebP)."
    )
    alt_text = models.CharField(
        "Alt Text / Accessibility Label",
        max_length=255,
        blank=True,
        help_text="Descriptive image caption for SEO and screen readers."
    )
    is_thumbnail = models.BooleanField(
        "Is Primary Thumbnail",
        default=False,
        db_index=True,
        help_text="Designates this image as the primary catalog card thumbnail."
    )
    order = models.PositiveIntegerField(
        "Display Sort Order",
        default=0,
        db_index=True,
        help_text="Ascending sequence for storefront carousel and gallery view."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['product', 'order'], name='idx_prod_img_order'),
            models.Index(fields=['product', 'is_thumbnail'], name='idx_prod_img_thumb'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                condition=models.Q(is_thumbnail=True),
                name='unique_primary_thumbnail_per_product'
            )
        ]

    def __str__(self):
        label = f"{self.product.name} - Image #{self.pk or 'new'}"
        if self.is_thumbnail:
            label += " (Thumbnail)"
        return label

    def save(self, *args, **kwargs):
        # 1. Enforce single-primary-thumbnail exclusivity per product atomically
        with transaction.atomic():
            if self.is_thumbnail and self.product_id:
                ProductImage.objects.filter(
                    product_id=self.product_id,
                    is_thumbnail=True
                ).exclude(pk=self.pk).update(is_thumbnail=False)

            # 2. Automatically optimize uploaded image to WebP
            compress_image(self.image, max_width=1200)
            super().save(*args, **kwargs)


# --- Signal Receivers for Variant Synchronization & Media Cleanup ---
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=ProductVariant)
@receiver(post_delete, sender=ProductVariant)
def update_product_on_variant_change(sender, instance, **kwargs):
    """
    Automatically re-synchronizes parent product aggregates (stock count, in-stock flag,
    and starting catalog price) whenever a child variant is created, modified, or deleted.
    """
    try:
        instance.product.sync_with_variants()
    except Product.DoesNotExist:
        # Cascade deletion safety: parent row was deleted before child post_delete signal
        pass


@receiver(post_delete, sender=ProductImage)
def delete_product_image_file(sender, instance, **kwargs):
    """
    Physically removes the image file from media storage when a ProductImage
    record is deleted, preventing orphaned binary files on disk / S3.
    """
    if instance.image:
        instance.image.delete(save=False)


class Review(models.Model):
    """
    Customer review and rating entity for a catalog product.
    Includes moderation status, verified-purchase certification,
    and a database-level unique constraint preventing duplicate reviews per user.
    """
    product = models.ForeignKey(
        Product,
        related_name='reviews',
        on_delete=models.CASCADE,
        help_text="Product being reviewed."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='reviews',
        on_delete=models.CASCADE,
        help_text="User who authored the review."
    )
    rating = models.PositiveSmallIntegerField(
        "Star Rating",
        choices=[(i, f"{i} Stars") for i in range(1, 6)],
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Customer satisfaction rating from 1 (lowest) to 5 (highest)."
    )
    comment = models.TextField(
        "Review Comment",
        blank=True,
        default='',
        help_text="Detailed customer feedback and experience description."
    )
    verified_purchase = models.BooleanField(
        "Verified Purchase",
        default=False,
        db_index=True,
        help_text="Indicates whether the author had a verified, delivered order for this product."
    )
    is_approved = models.BooleanField(
        "Approved for Display",
        default=True,
        db_index=True,
        help_text="Moderation flag controlling public storefront visibility."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Review"
        verbose_name_plural = "Product Reviews"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'is_approved', '-created_at'], name='idx_rev_prod_app_date'),
            models.Index(fields=['user', '-created_at'], name='idx_rev_user_date'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'user'],
                name='unique_user_product_review'
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.product.name} ({self.rating}★)"


class ReviewImage(models.Model):
    """
    Customer-uploaded photo attachment for a product review (unboxing, fit, texture).
    Automatically compressed to responsive WebP format.
    """
    review = models.ForeignKey(
        Review,
        related_name='images',
        on_delete=models.CASCADE,
        help_text="Parent review owning this image attachment."
    )
    image = models.ImageField(
        upload_to='reviews/',
        help_text="Customer photo attachment (automatically optimized to WebP)."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review Image"
        verbose_name_plural = "Review Images"
        ordering = ['id']

    def __str__(self):
        return f"Review #{self.review_id} Image #{self.pk or 'new'}"

    def save(self, *args, **kwargs):
        compress_image(self.image, max_width=800)
        super().save(*args, **kwargs)


@receiver(post_delete, sender=ReviewImage)
def delete_review_image_file(sender, instance, **kwargs):
    """
    Physically removes the image file from media storage when a ReviewImage
    record is deleted, preventing orphaned binary files on disk / S3.
    """
    if instance.image:
        instance.image.delete(save=False)


class Wishlist(models.Model):
    """
    Persistent customer product wishlist.
    Maintains a 1-to-1 relationship with the authenticated User and a M2M mapping with Product.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='wishlist',
        on_delete=models.CASCADE,
        help_text="User owning this saved wishlist."
    )
    products = models.ManyToManyField(
        Product,
        related_name='wishlisted_by',
        blank=True,
        help_text="Saved catalog products."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"

    def __str__(self):
        return f"Wishlist ({self.user.email})"

    def toggle(self, product: Product) -> tuple[bool, int]:
        """
        Atomically adds or removes a product from the wishlist.
        Returns a tuple: (is_added: bool, total_items_count: int).
        """
        if self.products.filter(pk=product.pk).exists():
            self.products.remove(product)
            added = False
        else:
            self.products.add(product)
            added = True
        return added, self.products.count()


class ActiveVisitor(models.Model):
    """
    Ephemeral storefront visitor presence record for real-time traffic monitoring
    and social proof urgency ("12 shoppers currently viewing this category").
    """
    session_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Anonymous session identifier or user token."
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address for telemetry and geolocation."
    )
    city = models.CharField(max_length=100, default='Unknown')
    region = models.CharField(max_length=100, default='Unknown')
    country = models.CharField(max_length=100, default='India')
    latitude = models.FloatField(default=20.5937)
    longitude = models.FloatField(default=78.9629)
    current_page = models.CharField(max_length=255, default='Shop')
    action = models.CharField(
        max_length=50,
        default='viewing',
        help_text="Current shopper intent action: viewing, cart, checkout, purchased."
    )
    last_activity = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Active Visitor"
        verbose_name_plural = "Active Visitors"
        ordering = ['-last_activity']

    def __str__(self):
        return f"{self.session_key[:8]}... - {self.city} ({self.action})"

    @classmethod
    def prune_stale(cls, timeout_minutes: int = 15) -> int:
        """
        Prunes visitor presence records older than timeout_minutes.
        Returns the number of deleted records.
        """
        from django.utils import timezone
        import datetime
        cutoff = timezone.now() - datetime.timedelta(minutes=timeout_minutes)
        deleted_count, _ = cls.objects.filter(last_activity__lt=cutoff).delete()
        return deleted_count
