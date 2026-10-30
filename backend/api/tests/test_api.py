import json
from decimal import Decimal

from rest_framework.test import APIClient

from api.models import Vendor
from api.services.erp_import import import_vendors, load_vendors_from_file
from simulated_erp.views import DATA_FILE

SIGN = {'invoice': 1, 'credit_memo': -1, 'payment': -1}


def expected_balances():
    """Each vendor's balance worked out straight from the ERP file, in Decimal."""
    with open(DATA_FILE, encoding='utf-8') as source:
        vendors = json.load(source)
    return {
        vendor['vendor_id']: sum(
            (SIGN[e['type']] * Decimal(str(e['amount'])) for e in vendor['ledger']), Decimal('0.00'),
        )
        for vendor in vendors
    }


def test_every_vendor_balance_matches_the_erp_data():
    import_vendors(load_vendors_from_file(DATA_FILE))

    response = APIClient().get('/api/vendors/')

    assert response.status_code == 200
    got = {row['erp_vendor_id']: row['balance'] for row in response.json()}
    assert got == {vendor_id: f'{balance:.2f}' for vendor_id, balance in expected_balances().items()}


def test_a_local_vendor_with_no_erp_record_has_no_balance():
    Vendor.objects.create(name='Coastal Ice Co.')

    [row] = APIClient().get('/api/vendors/').json()

    assert row['balance'] is None


def test_ledger_endpoint_returns_lines_and_totals_for_a_period():
    import_vendors(load_vendors_from_file(DATA_FILE))
    vendor = Vendor.objects.get(erp_vendor_id=1002)

    response = APIClient().get(f'/api/vendors/{vendor.pk}/ledger/', {'start': '2026-09-01', 'end': '2026-09-30'})

    body = response.json()
    assert response.status_code == 200
    assert all('2026-09-01' <= line['date'] <= '2026-09-30' for line in body['lines'])
    net = Decimal(body['total_invoiced']) - Decimal(body['total_credits']) - Decimal(body['total_paid'])
    assert Decimal(body['opening_balance']) + net == Decimal(body['balance'])


def test_ledger_rejects_a_bad_date():
    vendor = Vendor.objects.create(name='Coastal Ice Co.')

    response = APIClient().get(f'/api/vendors/{vendor.pk}/ledger/', {'start': '09/01/2026'})

    assert response.status_code == 400


def test_simulated_erp_only_includes_ledgers_when_asked():
    client = APIClient()

    without = client.get('/simulated-erp-api/vendors/').json()
    with_ledgers = client.get('/simulated-erp-api/vendors/', {'includeLedgers': 'true'}).json()

    assert 'ledger' not in without[0]
    assert 'ledger' in with_ledgers[0]
