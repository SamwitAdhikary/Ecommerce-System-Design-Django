from django.core.management.base import BaseCommand
from django.utils.timezone import now
from catalog.models import Product


class Command(BaseCommand):
    help = (
        "Audits and re-synchronizes parent product stock counts, in-stock flags, "
        "and starting catalog prices across all products with child variants."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Audit and report discrepancies without committing database modifications.'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        timestamp = now().isoformat()
        self.stdout.write(f"Starting catalog inventory synchronization audit at {timestamp}...")

        products_with_variants = Product.objects.filter(variants_list__isnull=False).distinct()
        total_products = products_with_variants.count()
        discrepancies_found = 0
        repaired_count = 0

        for product in products_with_variants:
            variants = list(product.variants_list.all())
            if not variants:
                continue

            expected_stock = sum(v.stock_count for v in variants)
            override_prices = [v.price_override for v in variants if v.price_override is not None]
            if any(v.price_override is None for v in variants):
                expected_price = min(override_prices + [product.price])
            elif override_prices:
                expected_price = min(override_prices)
            else:
                expected_price = product.price
            expected_in_stock = (expected_stock > 0)

            has_stock_mismatch = (product.stock_count != expected_stock)
            has_price_mismatch = (product.price != expected_price)
            has_instock_mismatch = (product.in_stock != expected_in_stock)

            if has_stock_mismatch or has_price_mismatch or has_instock_mismatch:
                discrepancies_found += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Discrepancy on Product ID {product.pk} ('{product.name}'):\n"
                        f"  - Stock: Current={product.stock_count}, Expected={expected_stock}\n"
                        f"  - Price: Current=Rs.{product.price}, Expected=Rs.{expected_price}\n"
                        f"  - In Stock: Current={product.in_stock}, Expected={expected_in_stock}"
                    )
                )

                if not dry_run:
                    product.sync_with_variants()
                    repaired_count += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN COMPLETE: Audited {total_products} products. "
                    f"Found {discrepancies_found} discrepancies (0 modified)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"SYNCHRONIZATION COMPLETE: Audited {total_products} products. "
                    f"Found and reconciled {repaired_count} discrepancies."
                )
            )
