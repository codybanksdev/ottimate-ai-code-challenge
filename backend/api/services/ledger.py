from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from api.models import LedgerEntry, Vendor

ZERO = Decimal('0.00')


@dataclass
class LedgerLine:
    entry: LedgerEntry
    running_balance: Decimal


@dataclass
class Ledger:
    vendor: Vendor
    start: Optional[date]
    end: Optional[date]
    # The balance carried in from before `start`; zero when there is no start.
    opening_balance: Decimal
    lines: list
    # Totals for the lines shown, i.e. for the period. Each keeps the ERP's
    # sign, so voids and reversals net out.
    total_invoiced: Decimal
    total_credits: Decimal
    total_paid: Decimal
    # The balance after the last line shown: the amount owed as of `end`.
    balance: Decimal
    # Entries the ERP has since removed. Listed for audit, counted nowhere.
    removed_entries: list


def build_ledger(vendor, start=None, end=None):
    """Return the vendor's ledger entries oldest-first with a running balance.

    A positive balance is money owed to the vendor; a negative one is a credit
    the vendor owes back (or that can be applied to future invoices).

    With a date range, entries before `start` are rolled into
    `opening_balance` and the running balance carries on from there, so every
    row still shows the true balance on that day rather than a sum of the
    visible rows. Entries after `end` are left out, which makes `balance` the
    balance as of `end`.
    """
    entries = sorted(vendor.entries.all(), key=lambda e: (e.date, e.erp_id))

    opening_balance = ZERO
    totals = {t: ZERO for t in LedgerEntry.Type.values}
    lines = []
    removed_entries = []
    balance = ZERO
    for entry in entries:
        if entry.removed_from_erp_at is not None:
            removed_entries.append(entry)
            continue
        if end is not None and entry.date > end:
            continue
        balance += entry.balance_effect
        if start is not None and entry.date < start:
            opening_balance = balance
            continue
        totals[entry.type] += entry.amount
        lines.append(LedgerLine(entry=entry, running_balance=balance))

    return Ledger(
        vendor=vendor,
        start=start,
        end=end,
        opening_balance=opening_balance,
        lines=lines,
        total_invoiced=totals[LedgerEntry.Type.INVOICE],
        total_credits=totals[LedgerEntry.Type.CREDIT_MEMO],
        total_paid=totals[LedgerEntry.Type.PAYMENT],
        balance=balance,
        removed_entries=removed_entries,
    )
