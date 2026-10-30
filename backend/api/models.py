from django.db import models
from django.db.models import Case, DecimalField, F, Q, Sum, When


class VendorQuerySet(models.QuerySet):
    def with_balance(self, as_of=None):
        """Annotate each vendor with `balance`, the amount currently owed to it.

        Invoices add to the balance; credit memos and payments reduce it.
        Amounts keep the sign the ERP sent, so a voided payment (a negative
        payment) adds back to the balance and a reversed credit memo (a
        negative credit memo) does too.

        The balance is None for a vendor with no ledger entries at all, so
        callers can tell "nothing on file" from "settled at zero". Entries the
        ERP has removed are left out.

        With `as_of`, only entries dated on or before it count, which gives
        each vendor's balance at the close of that day.
        """
        money = DecimalField(max_digits=12, decimal_places=2)
        counted = Q(entries__removed_from_erp_at__isnull=True)
        if as_of is not None:
            counted &= Q(entries__date__lte=as_of)
        return self.annotate(
            balance=Sum(
                Case(
                    When(entries__type=LedgerEntry.Type.INVOICE, then=F('entries__amount')),
                    default=-F('entries__amount'),
                    output_field=money,
                ),
                filter=counted,
            ),
        )


class Vendor(models.Model):
    # The vendor's identifier in the ERP. Local ids are assigned by this
    # database and are unrelated to it, so the two must never be compared.
    # Null for vendors that exist locally but have not been matched to the ERP.
    erp_vendor_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    # Days from invoice date to due date, e.g. 30 for "Net 30".
    payment_terms_days = models.PositiveIntegerField(null=True, blank=True)
    # When this vendor's ledger was last brought in line with the ERP. Null if
    # it never has been.
    ledger_synced_at = models.DateTimeField(null=True, blank=True)

    objects = VendorQuerySet.as_manager()

    def __str__(self):
        return self.name


class LedgerEntry(models.Model):
    class Type(models.TextChoices):
        INVOICE = 'invoice', 'Invoice'
        CREDIT_MEMO = 'credit_memo', 'Credit memo'
        PAYMENT = 'payment', 'Payment'

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='entries')
    # The entry's identifier in the ERP (a string in the API).
    erp_id = models.CharField(max_length=64)
    type = models.CharField(max_length=16, choices=Type.choices)
    date = models.DateField()
    # Invoice number, credit memo number, or payment reference (check/ACH).
    document_number = models.CharField(max_length=64)
    description = models.CharField(max_length=255, blank=True)
    # Stored exactly as the ERP sends it. The sign is not the direction of the
    # entry -- `type` is. Use `balance_effect` when adding entries up.
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # Invoices only.
    due_date = models.DateField(null=True, blank=True)
    # Invoices and credit memos: the expense account and restaurant location
    # the amount is coded to. Payments have neither.
    gl_account_code = models.CharField(max_length=16, blank=True)
    gl_account_name = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    # Credit memos and payments: which invoices they settle, as the ERP sent
    # it -- a list of {"invoice_number": str, "amount": str}. Empty when the
    # credit or payment is unapplied.
    applies_to = models.JSONField(default=list, blank=True)
    # Set when an import finds the ERP no longer has this entry. The row is
    # kept so there is a record of why a balance changed, but it no longer
    # counts toward the balance.
    removed_from_erp_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = 'ledger entries'
        constraints = [
            models.UniqueConstraint(fields=['vendor', 'erp_id'], name='unique_erp_entry_per_vendor'),
        ]

    @property
    def balance_effect(self):
        """How much this entry changes what is owed to the vendor."""
        return self.amount if self.type == self.Type.INVOICE else -self.amount

    def __str__(self):
        return f'{self.date} {self.type} {self.document_number} ({self.amount})'
