from django.core.management.base import BaseCommand

from api.models import Vendor


class Command(BaseCommand):
    help = 'Seeds the database with a vendor that was entered by hand and is not in the ERP.'

    def handle(self, *args, **options):
        # Entered locally by the AP team. It has no ERP id, so the import
        # never matches it to anything.
        Vendor.objects.get_or_create(
            name='Coastal Ice Co.', erp_vendor_id=None, defaults={'payment_terms_days': 15},
        )
        self.stdout.write('Seeded local vendors.')
