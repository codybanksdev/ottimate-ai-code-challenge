from django.core.management.base import BaseCommand, CommandError

from api.models import Vendor
from api.services.erp_import import (
    ERPImportError, fetch_vendors_with_ledgers, import_vendors, load_vendors_from_file,
)


class Command(BaseCommand):
    help = 'Imports vendors and their ledgers from the ERP integration API into the local database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            help='Import from a saved ERP response (JSON file) instead of calling the API.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what the import would change without writing anything.',
        )

    def handle(self, *args, **options):
        try:
            if options['source']:
                vendors_data = load_vendors_from_file(options['source'])
            else:
                vendors_data = fetch_vendors_with_ledgers()
        except ERPImportError as e:
            raise CommandError(str(e))

        dry_run = options['dry_run']
        result = import_vendors(vendors_data, dry_run=dry_run)
        if dry_run:
            self.stdout.write('Dry run: nothing was written. This is what would change:')

        self.stdout.write(f'Vendors: {result.vendors_created} created.')
        self.stdout.write(
            f'Ledger entries: {result.entries_created} created, {result.entries_updated} updated, '
            f'{result.entries_removed} marked removed (no longer in the ERP), '
            f'{result.entries_restored} restored.'
        )
        # After a dry run the database is unchanged, so this list would be the
        # state before the import, not after it.
        unlinked = Vendor.objects.none() if dry_run else Vendor.objects.filter(erp_vendor_id__isnull=True)
        for vendor in unlinked:
            self.stderr.write(f'Local vendor {vendor.id} ({vendor.name}) has no match in the ERP and has no ledger.')
        for error in result.errors:
            self.stderr.write(error)
        if result.errors:
            raise CommandError(f'Import finished with {len(result.errors)} error(s).')
