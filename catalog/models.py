from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
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
