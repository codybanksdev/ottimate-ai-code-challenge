"""Sync vendors and their ledgers from the ERP integration API.

See simulated_erp/API_SPEC.md for the upstream contract.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import Error as DatabaseError
from django.db import transaction as db_transaction
from django.utils import timezone

from api.models import LedgerEntry, Vendor

REQUEST_TIMEOUT_SECONDS = 30
CENT = Decimal('0.01')
# LedgerEntry.amount holds 10 digits before the decimal point.
MAX_AMOUNT = Decimal('9999999999.99')
ENTRY_FIELDS = [
    'type', 'date', 'document_number', 'description', 'amount', 'due_date',
    'gl_account_code', 'gl_account_name', 'location', 'applies_to',
]

logger = logging.getLogger(__name__)


class ERPImportError(Exception):
    """The ERP response could not be fetched or is not shaped as the spec says."""


class InvalidLedgerEntry(ValueError):
    pass


@dataclass
class ImportResult:
    vendors_created: int = 0
    entries_created: int = 0
    entries_updated: int = 0
    entries_removed: int = 0
    entries_restored: int = 0
    # One message per vendor whose ledger was left untouched.
    errors: list = field(default_factory=list)


def fetch_vendors_with_ledgers():
    # Without includeLedgers the API returns vendors with no `ledger` key.
    url = settings.ERP_API_URL.rstrip('/') + '/vendors/'
    try:
        response = requests.get(url, params={'includeLedgers': 'true'}, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.exceptions.RequestException, ValueError) as exc:
        raise ERPImportError(f'Error fetching data from the ERP API at {url}: {exc}') from exc
    return _require_vendor_list(payload)


def load_vendors_from_file(path):
    """Read a saved ERP vendors response instead of calling the API."""
    try:
        with open(path, encoding='utf-8') as source:
            payload = json.load(source)
    except (OSError, ValueError) as exc:
        raise ERPImportError(f'Error reading {path}: {exc}') from exc
    return _require_vendor_list(payload)


def _require_vendor_list(payload):
    if not isinstance(payload, list):
        raise ERPImportError('ERP data is not a list of vendors.')
    return payload


def _parse_amount(value):
    # str() first: Decimal(1882.43) would carry the float's binary error.
    amount = Decimal(str(value))
    if not amount.is_finite() or amount != amount.quantize(CENT):
        raise InvalidLedgerEntry(f'amount {value!r} is not a whole number of cents')
    if abs(amount) > MAX_AMOUNT:
        raise InvalidLedgerEntry(f'amount {value!r} is too large to store')
    return amount.quantize(CENT)


def _parse_date(value):
    # strptime, not date.fromisoformat, which also accepts 20230105.
    return datetime.strptime(value, '%Y-%m-%d').date()


def parse_ledger_entry(entry):
    """Validate one ERP ledger entry and return LedgerEntry field values."""
    try:
        erp_id = entry['id']
        if erp_id is None or str(erp_id) == '':
            raise InvalidLedgerEntry('missing id')
        entry_type = entry['type']
        if entry_type not in LedgerEntry.Type.values:
            raise InvalidLedgerEntry(f'unknown type {entry_type!r}')
        gl_account = entry.get('gl_account') or {}
        if not isinstance(gl_account, dict):
            raise InvalidLedgerEntry(f'gl_account {gl_account!r} is not an object')
        applies_to = [
            # Stored as strings so the amounts stay exact in JSON.
            {'invoice_number': str(item['invoice_number']), 'amount': str(_parse_amount(item['amount']))}
            for item in entry.get('applies_to') or []
        ]
        return {
            'erp_id': str(erp_id),
            'type': entry_type,
            'date': _parse_date(entry['date']),
            'document_number': str(entry.get('document_number') or ''),
            'description': entry.get('description') or '',
            'amount': _parse_amount(entry['amount']),
            'due_date': _parse_date(entry['due_date']) if entry.get('due_date') else None,
            'gl_account_code': str(gl_account.get('code') or ''),
            'gl_account_name': gl_account.get('name') or '',
            'location': entry.get('location') or '',
            'applies_to': applies_to,
        }
    except InvalidLedgerEntry:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, InvalidOperation) as exc:
        raise InvalidLedgerEntry(f'{type(exc).__name__}: {exc}') from exc


def _resolve_vendor(vendor_data, result):
    """Find or create the local vendor for an ERP vendor.

    The ERP id is the only key. A local vendor with the same name but no ERP
    id is not assumed to be the same vendor: putting a ledger on the wrong
    vendor is worse than showing both.
    """
    erp_vendor_id = vendor_data['vendor_id']
    terms = vendor_data.get('payment_terms_days')
    if terms is not None and (not isinstance(terms, int) or isinstance(terms, bool) or terms < 0):
        raise InvalidLedgerEntry(f'payment_terms_days {terms!r} is not a whole number of days')
    vendor = Vendor.objects.filter(erp_vendor_id=erp_vendor_id).first()
    if vendor is None:
        vendor = Vendor(erp_vendor_id=erp_vendor_id)
        result.vendors_created += 1
    vendor.name = vendor_data.get('name') or ''
    vendor.payment_terms_days = terms
    vendor.save()
    return vendor


def _sync_ledger(vendor, ledger, result, synced_at):
    """Make the vendor's local entries match the ERP ledger exactly."""
    parsed = [parse_ledger_entry(entry) for entry in ledger]
    erp_ids = [values['erp_id'] for values in parsed]
    if len(set(erp_ids)) != len(erp_ids):
        raise InvalidLedgerEntry('duplicate entry id in ledger')

    existing = {e.erp_id: e for e in vendor.entries.all()}
    live = [e for e in existing.values() if e.removed_from_erp_at is None]
    if live and not parsed:
        # A vendor that had entries and now has none looks like a bad
        # response, and acting on it would zero the balance. Refuse, and let a
        # person decide.
        raise InvalidLedgerEntry(f'the ERP returned an empty ledger but {len(live)} entries are on file')

    to_create, to_update = [], []
    for values in parsed:
        current = existing.pop(values['erp_id'], None)
        if current is None:
            to_create.append(LedgerEntry(vendor=vendor, **values))
            continue
        changed = any(getattr(current, name) != values[name] for name in ENTRY_FIELDS)
        restored = current.removed_from_erp_at is not None
        if changed or restored:
            for name in ENTRY_FIELDS:
                setattr(current, name, values[name])
            current.removed_from_erp_at = None
            to_update.append(current)
            if restored:
                result.entries_restored += 1
            else:
                result.entries_updated += 1

    LedgerEntry.objects.bulk_create(to_create)
    LedgerEntry.objects.bulk_update(to_update, ENTRY_FIELDS + ['removed_from_erp_at'])
    # Whatever is left locally is no longer in the ERP ledger. It stops
    # counting toward the balance, so the balance still matches the ERP, but
    # the row is kept to explain why the balance changed.
    newly_removed = [e.pk for e in existing.values() if e.removed_from_erp_at is None]
    LedgerEntry.objects.filter(pk__in=newly_removed).update(removed_from_erp_at=synced_at)

    vendor.ledger_synced_at = synced_at
    vendor.save(update_fields=['ledger_synced_at'])

    result.entries_created += len(to_create)
    result.entries_removed += len(newly_removed)


def import_vendors(vendors_data, dry_run=False):
    """Apply an ERP vendors payload to the local database.

    With `dry_run`, everything runs and is counted, then rolled back.
    """
    if dry_run:
        # One outer transaction that is always rolled back. Each vendor's own
        # atomic block becomes a savepoint inside it.
        with db_transaction.atomic():
            result = _import_vendors(vendors_data)
            db_transaction.set_rollback(True)
    else:
        # No outer transaction: each vendor commits on its own, so a failure
        # partway through leaves the vendors already done in place.
        result = _import_vendors(vendors_data)
    logger.info(
        'ERP import finished (dry_run=%s): %s vendors in payload, %s created; entries %s created, '
        '%s updated, %s removed, %s restored; %s ledgers skipped',
        dry_run, len(vendors_data), result.vendors_created, result.entries_created,
        result.entries_updated, result.entries_removed, result.entries_restored, len(result.errors),
    )
    return result


def _import_vendors(vendors_data):
    """Apply the payload vendor by vendor.

    Each vendor is applied in its own database transaction. If any entry in a
    vendor's ledger is invalid, that vendor is left exactly as it was and
    reported in `ImportResult.errors`: a partly imported ledger shows a
    plausible but wrong balance, which is worse than a stale one.
    """
    result = ImportResult()
    synced_at = timezone.now()
    seen = set()
    for vendor_data in vendors_data:
        erp_vendor_id = vendor_data.get('vendor_id') if isinstance(vendor_data, dict) else None
        if not isinstance(erp_vendor_id, int) or isinstance(erp_vendor_id, bool) or erp_vendor_id < 0:
            result.errors.append(f'Skipped a vendor with no usable vendor_id: {erp_vendor_id!r}')
            continue
        if erp_vendor_id in seen:
            # Syncing the second copy would mark the first copy's entries as
            # removed. Keep the first and say so.
            result.errors.append(f'ERP vendor {erp_vendor_id}: appears more than once. Only the first was used.')
            continue
        seen.add(erp_vendor_id)
        ledger = vendor_data.get('ledger')
        if not isinstance(ledger, list):
            result.errors.append(f'ERP vendor {erp_vendor_id}: response has no ledger. Skipped.')
            continue
        vendor_result = ImportResult()
        try:
            with db_transaction.atomic():
                vendor = _resolve_vendor(vendor_data, vendor_result)
                _sync_ledger(vendor, ledger, vendor_result, synced_at)
        except (InvalidLedgerEntry, DatabaseError) as exc:
            # The atomic block has already rolled this vendor back.
            logger.warning('ERP vendor %s ledger skipped: %s', erp_vendor_id, exc)
            result.errors.append(f'ERP vendor {erp_vendor_id}: {exc}. Ledger left unchanged.')
            continue
        # Only counted once this vendor's block has completed.
        result.vendors_created += vendor_result.vendors_created
        result.entries_created += vendor_result.entries_created
        result.entries_updated += vendor_result.entries_updated
        result.entries_removed += vendor_result.entries_removed
        result.entries_restored += vendor_result.entries_restored
    return result
