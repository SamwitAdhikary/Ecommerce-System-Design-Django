from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError


class SiteSettings(models.Model):
    """
    Singleton model representing global e-commerce storefront configuration,
    order constraints, default shipping tariffs, and payment surcharges.
    """
    site_name = models.CharField(
        max_length=150,
        default='Modern Storefront',
        help_text="Public brand name displayed across the storefront"
    )
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Customer support email address"
    )
    contact_phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Customer support contact phone number"
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Physical headquarters or registered business address"
    )

    # Storefront Operating State
    maintenance_mode = models.BooleanField(
        default=False,
        help_text="When enabled, non-admin checkout and order placement are disabled"
    )

    # Order Value Constraints
    minimum_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Minimum cart subtotal required to proceed to checkout"
    )

    # Global Shipping Configuration
    standard_shipping_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text="Default flat shipping fee applied if zone shipping is disabled or unlisted"
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('999.00'),
        help_text="Cart subtotal threshold at or above which shipping is free"
    )

    # Cash On Delivery & Surcharge Configuration
    cod_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('40.00'),
        help_text="Flat handling surcharge applied to Cash On Delivery (COD) orders"
    )
    is_zone_shipping_enabled = models.BooleanField(
        default=False,
        help_text="When enabled, dynamic geographic zones override global shipping rates"
    )
    partial_cod_deposit_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Percentage of order total required as advance deposit for COD orders (0 to 100)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return f"{self.site_name} Configuration"

    def save(self, *args, **kwargs):
        """
        Enforce the Singleton pattern at the ORM layer.
        Any attempt to save a new instance assigns it the primary key of the
        existing record, ensuring only one row exists in the database.
        """
        if not self.pk and SiteSettings.objects.exists():
            existing = SiteSettings.objects.first()
            self.pk = existing.pk
            if self.created_at is None:
                self.created_at = existing.created_at
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of the singleton instance."""
        raise ValidationError("The singleton SiteSettings instance cannot be deleted.")

    @classmethod
    def get_solo(cls):
        """
        Retrieves or creates the single global configuration record.
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def calculate_shipping(self, state=None, subtotal=Decimal('0.00'), is_cod=False):
        """
        Calculates dynamic delivery fees, free shipping eligibility, and COD surcharges
        based on destination state, cart subtotal, and payment method.
        """
        if not isinstance(subtotal, Decimal):
            subtotal = Decimal(str(subtotal))

        # Default to global configuration
        effective_shipping_fee = self.standard_shipping_fee
        effective_free_threshold = self.free_shipping_threshold
        effective_cod_charge = self.cod_charge
        matched_zone_name = "Global Default"

        # Evaluate Zone-based shipping if active
        if self.is_zone_shipping_enabled and state:
            matched_zone = ShippingZone.resolve_for_state(state)
            if matched_zone:
                effective_shipping_fee = matched_zone.shipping_fee
                if matched_zone.free_shipping_threshold is not None:
                    effective_free_threshold = matched_zone.free_shipping_threshold
                if matched_zone.cod_charge is not None:
                    effective_cod_charge = matched_zone.cod_charge
                matched_zone_name = matched_zone.name

        # Calculate Free Shipping Eligibility
        is_free_shipping = subtotal >= effective_free_threshold
        if is_free_shipping:
            applied_shipping_fee = Decimal('0.00')
            amount_needed_for_free_shipping = Decimal('0.00')
        else:
            applied_shipping_fee = effective_shipping_fee
            amount_needed_for_free_shipping = max(Decimal('0.00'), effective_free_threshold - subtotal)

        applied_cod_fee = effective_cod_charge if is_cod else Decimal('0.00')
        estimated_total = subtotal + applied_shipping_fee + applied_cod_fee
        meets_minimum_order = subtotal >= self.minimum_order_value

        return {
            'state': state or '',
            'matched_zone': matched_zone_name,
            'subtotal': subtotal,
            'shipping_fee': applied_shipping_fee,
            'standard_zone_fee': effective_shipping_fee,
            'is_free_shipping': is_free_shipping,
            'free_shipping_threshold': effective_free_threshold,
            'amount_needed_for_free_shipping': amount_needed_for_free_shipping,
            'cod_charge': applied_cod_fee,
            'is_cod': is_cod,
            'estimated_total': estimated_total,
            'minimum_order_value': self.minimum_order_value,
            'meets_minimum_order': meets_minimum_order,
            'maintenance_mode': self.maintenance_mode,
        }


class ShippingZone(models.Model):
    """
    Geographic delivery zone defining regional shipping tariffs, customized
    free-shipping thresholds, and COD surcharges based on state/province matching.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Descriptive zone label (e.g. 'West Zone (Tier 1)', 'North East & Special States')"
    )
    states = models.TextField(
        help_text="Comma-separated list of state names or codes (e.g. 'Maharashtra, Gujarat, Goa')"
    )
    shipping_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text="Standard delivery fee for this geographic zone"
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Zone override for free shipping threshold. Leave blank to inherit site settings default."
    )
    cod_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Zone override for COD fee. Leave blank to inherit site settings default."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only active zones are evaluated during rate resolution"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Shipping Zone"
        verbose_name_plural = "Shipping Zones"

    def __str__(self):
        return f"{self.name} (₹{self.shipping_fee})"

    def get_state_list(self):
        """
        Parses the comma-separated state string into a clean list of lowercase tokens.
        """
        if not self.states:
            return []
        return [s.strip().lower() for s in self.states.split(',') if s.strip()]

    def matches_state(self, state_query):
        """
        Evaluates whether a given state name or code matches this zone.
        """
        if not state_query:
            return False
        query = state_query.strip().lower()
        return query in self.get_state_list()

    @classmethod
    def resolve_for_state(cls, state_name):
        """
        Iterates over active shipping zones to find the first matching zone for the state.
        """
        if not state_name:
            return None
        for zone in cls.objects.filter(is_active=True):
            if zone.matches_state(state_name):
                return zone
        return None
