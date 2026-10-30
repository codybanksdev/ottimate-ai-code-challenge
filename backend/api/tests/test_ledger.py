from datetime import date
from decimal import Decimal

from api.models import LedgerEntry, Vendor
from api.services.ledger import build_ledger


def add(vendor, erp_id, day, type, amount, **fields):
    return LedgerEntry.objects.create(
        vendor=vendor, erp_id=erp_id, date=date.fromisoformat(day), type=type,
        document_number=fields.pop('document_number', erp_id), amount=Decimal(amount), **fields,
    )


def balances(ledger):
    return [line.running_balance for line in ledger.lines]


def test_invoices_add_and_credit_memos_and_payments_subtract():
    vendor = Vendor.objects.create(name='Valley Creamery')
    add(vendor, 'E-1', '2026-01-02', 'invoice', '1000.00')
    add(vendor, 'E-2', '2026-01-05', 'credit_memo', '150.25')
    add(vendor, 'E-3', '2026-01-20', 'payment', '600.00')

    ledger = build_ledger(vendor)

    assert balances(ledger) == [Decimal('1000.00'), Decimal('849.75'), Decimal('249.75')]
    assert ledger.balance == Decimal('249.75')
    assert ledger.total_invoiced == Decimal('1000.00')
    assert ledger.total_credits == Decimal('150.25')
    assert ledger.total_paid == Decimal('600.00')


def test_a_void_and_a_credit_reversal_keep_their_sign_and_add_back():
    vendor = Vendor.objects.create(name='Harborview Seafood')
    add(vendor, 'E-1', '2026-01-02', 'invoice', '500.00')
    add(vendor, 'E-2', '2026-01-03', 'credit_memo', '50.00')
    add(vendor, 'E-3', '2026-01-04', 'credit_memo', '-50.00')
    add(vendor, 'E-4', '2026-01-10', 'payment', '500.00')
    add(vendor, 'E-5', '2026-01-12', 'payment', '-500.00')

    ledger = build_ledger(vendor)

    assert balances(ledger) == [
        Decimal('500.00'), Decimal('450.00'), Decimal('500.00'), Decimal('0.00'), Decimal('500.00'),
    ]
    assert ledger.total_credits == Decimal('0.00')
    assert ledger.total_paid == Decimal('0.00')


def test_lines_are_ordered_by_date_then_erp_id():
    vendor = Vendor.objects.create(name='Pacific Coast Produce')
    add(vendor, 'E-3', '2026-02-01', 'invoice', '10.00')
    add(vendor, 'E-2', '2026-01-01', 'invoice', '20.00')
    add(vendor, 'E-1', '2026-02-01', 'payment', '5.00')

    assert [line.entry.erp_id for line in build_ledger(vendor).lines] == ['E-2', 'E-1', 'E-3']


def test_a_date_range_carries_an_opening_balance():
    vendor = Vendor.objects.create(name='Golden Gate Broadline Foods')
    add(vendor, 'E-1', '2026-01-05', 'invoice', '300.00')
    add(vendor, 'E-2', '2026-02-05', 'invoice', '200.00')
    add(vendor, 'E-3', '2026-02-20', 'payment', '300.00')
    add(vendor, 'E-4', '2026-03-05', 'invoice', '100.00')

    ledger = build_ledger(vendor, start=date(2026, 2, 1), end=date(2026, 2, 28))

    assert ledger.opening_balance == Decimal('300.00')
    assert balances(ledger) == [Decimal('500.00'), Decimal('200.00')]
    assert ledger.balance == Decimal('200.00')
    assert ledger.total_invoiced == Decimal('200.00')


def test_entries_removed_from_the_erp_are_listed_but_not_counted():
    from django.utils import timezone

    vendor = Vendor.objects.create(name='Bayline Paper & Packaging')
    add(vendor, 'E-1', '2026-01-05', 'invoice', '300.00')
    add(vendor, 'E-2', '2026-01-06', 'invoice', '75.00', removed_from_erp_at=timezone.now())

    ledger = build_ledger(vendor)

    assert ledger.balance == Decimal('300.00')
    assert [e.erp_id for e in ledger.removed_entries] == ['E-2']


def test_with_balance_agrees_with_build_ledger():
    vendor = Vendor.objects.create(name='CleanFold Linen Service')
    add(vendor, 'E-1', '2026-01-05', 'invoice', '610.10')
    add(vendor, 'E-2', '2026-01-06', 'credit_memo', '10.10')
    add(vendor, 'E-3', '2026-02-01', 'payment', '600.00')
    add(vendor, 'E-4', '2026-02-02', 'payment', '-600.00')

    annotated = Vendor.objects.with_balance().get(pk=vendor.pk)
    as_of = Vendor.objects.with_balance(as_of=date(2026, 2, 1)).get(pk=vendor.pk)

    assert annotated.balance.quantize(Decimal('0.01')) == build_ledger(vendor).balance == Decimal('600.00')
    assert as_of.balance.quantize(Decimal('0.01')) == Decimal('0.00')
