import copy
from decimal import Decimal

import pytest

from api.models import LedgerEntry, Vendor
from api.services.erp_import import (
    ERPImportError, InvalidLedgerEntry, import_vendors, load_vendors_from_file, parse_ledger_entry,
)

INVOICE = {
    'id': 'E-1', 'type': 'invoice', 'date': '2026-01-05', 'document_number': 'VC-100',
    'amount': 1882.43, 'description': 'Dairy order', 'due_date': '2026-01-20',
    'gl_account': {'code': '5000', 'name': 'Food Cost'}, 'location': 'Mission',
}
PAYMENT = {
    'id': 'E-2', 'type': 'payment', 'date': '2026-01-21', 'document_number': 'ACH-1',
    'amount': 1882.43, 'description': 'ACH payment ACH-1',
    'applies_to': [{'invoice_number': 'VC-100', 'amount': 1882.43}],
}


def payload(*ledger, vendor_id=1004, name='Valley Creamery'):
    return [{'vendor_id': vendor_id, 'name': name, 'payment_terms_days': 15, 'ledger': list(ledger)}]


def test_parse_keeps_cents_exact_and_reads_every_field():
    values = parse_ledger_entry(INVOICE)

    assert values['amount'] == Decimal('1882.43')
    assert values['gl_account_code'] == '5000'
    assert values['location'] == 'Mission'
    assert str(values['due_date']) == '2026-01-20'
    assert parse_ledger_entry(PAYMENT)['applies_to'] == [{'invoice_number': 'VC-100', 'amount': '1882.43'}]


@pytest.mark.parametrize('change', [
    {'type': 'debit_memo'},
    {'amount': 10.001},
    {'date': '01/05/2026'},
    {'id': ''},
])
def test_parse_rejects_entries_that_do_not_match_the_spec(change):
    with pytest.raises(InvalidLedgerEntry):
        parse_ledger_entry({**INVOICE, **change})


def test_import_creates_vendors_and_entries_matched_on_erp_id():
    Vendor.objects.create(name='Valley Creamery')  # local only, never matched by name

    result = import_vendors(payload(INVOICE, PAYMENT))

    vendor = Vendor.objects.get(erp_vendor_id=1004)
    assert result.vendors_created == 1
    assert result.entries_created == 2
    assert vendor.entries.count() == 2
    assert vendor.ledger_synced_at is not None
    assert Vendor.objects.filter(erp_vendor_id__isnull=True).count() == 1


def test_import_is_safe_to_rerun():
    import_vendors(payload(INVOICE, PAYMENT))
    result = import_vendors(payload(INVOICE, PAYMENT))

    assert (result.vendors_created, result.entries_created, result.entries_updated) == (0, 0, 0)
    assert LedgerEntry.objects.count() == 2


def test_changed_entries_are_updated_and_missing_ones_marked_removed():
    import_vendors(payload(INVOICE, PAYMENT))

    result = import_vendors(payload({**INVOICE, 'amount': 1900.00}))

    assert result.entries_updated == 1
    assert result.entries_removed == 1
    assert LedgerEntry.objects.get(erp_id='E-1').amount == Decimal('1900.00')
    assert LedgerEntry.objects.get(erp_id='E-2').removed_from_erp_at is not None


def test_one_bad_entry_leaves_that_vendor_untouched_but_imports_the_others():
    data = payload(INVOICE) + payload({**INVOICE, 'type': 'mystery'}, vendor_id=1005, name='Redwood')

    result = import_vendors(data)

    assert Vendor.objects.filter(erp_vendor_id=1004).exists()
    assert not Vendor.objects.filter(erp_vendor_id=1005).exists()
    assert len(result.errors) == 1 and '1005' in result.errors[0]


def test_an_empty_ledger_does_not_wipe_a_vendor_with_entries():
    import_vendors(payload(INVOICE))

    result = import_vendors(payload())

    assert len(result.errors) == 1
    assert LedgerEntry.objects.get(erp_id='E-1').removed_from_erp_at is None


def test_dry_run_writes_nothing():
    result = import_vendors(payload(INVOICE, PAYMENT), dry_run=True)

    assert result.entries_created == 2
    assert Vendor.objects.count() == 0


def test_load_from_file_rejects_a_payload_that_is_not_a_list(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{"vendors": []}')

    with pytest.raises(ERPImportError):
        load_vendors_from_file(path)


def test_voids_and_applications_survive_the_round_trip():
    void = copy.deepcopy(PAYMENT)
    void.update(id='E-3', amount=-1882.43, description='Void of ACH-1')
    void['applies_to'][0]['amount'] = -1882.43

    import_vendors(payload(INVOICE, PAYMENT, void))

    entry = LedgerEntry.objects.get(erp_id='E-3')
    assert entry.amount == Decimal('-1882.43')
    assert entry.applies_to == [{'invoice_number': 'VC-100', 'amount': '-1882.43'}]


def test_a_malformed_gl_account_is_reported_and_later_vendors_still_import():
    data = (payload({**INVOICE, 'gl_account': ['5000']}, vendor_id=1005, name='Redwood')
            + payload(INVOICE))

    result = import_vendors(data)

    assert len(result.errors) == 1 and '1005' in result.errors[0]
    assert Vendor.objects.filter(erp_vendor_id=1004).exists()


@pytest.mark.parametrize('terms', ['Net 30', -1, 2.5])
def test_bad_payment_terms_are_reported_not_raised(terms):
    data = payload(INVOICE)
    data[0]['payment_terms_days'] = terms

    result = import_vendors(data)

    assert len(result.errors) == 1
    assert not Vendor.objects.exists()
