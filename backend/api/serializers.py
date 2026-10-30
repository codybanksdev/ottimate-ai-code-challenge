from decimal import Decimal

from rest_framework import serializers

from api.models import LedgerEntry, Vendor

CENT = Decimal('0.01')


def money(**kwargs):
    return serializers.DecimalField(max_digits=14, decimal_places=2, **kwargs)


class VendorSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id', 'erp_vendor_id', 'name', 'payment_terms_days', 'ledger_synced_at']


class VendorSerializer(VendorSummarySerializer):
    balance = serializers.SerializerMethodField()

    class Meta(VendorSummarySerializer.Meta):
        fields = VendorSummarySerializer.Meta.fields + ['balance']

    def get_balance(self, vendor):
        """The amount owed to the vendor, or null when there is nothing to base one on.

        Requires a queryset built with `Vendor.objects.with_balance()`. A
        vendor with no ERP record and no entries has no balance: showing $0.00
        would claim the account is settled.
        """
        if vendor.balance is None:
            return '0.00' if vendor.erp_vendor_id is not None else None
        # SQLite adds decimals up in floating point, so a settled vendor can sum
        # to -1.1e-13. Round to cents, then + 0 turns the resulting -0.00 into 0.00.
        return str(vendor.balance.quantize(CENT) + 0)


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = [
            'id', 'erp_id', 'vendor', 'type', 'date', 'document_number', 'description', 'amount',
            'due_date', 'gl_account_code', 'gl_account_name', 'location', 'applies_to',
            'removed_from_erp_at',
        ]


class LedgerLineSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='entry.id')
    erp_id = serializers.CharField(source='entry.erp_id')
    type = serializers.CharField(source='entry.type')
    date = serializers.DateField(source='entry.date')
    document_number = serializers.CharField(source='entry.document_number')
    description = serializers.CharField(source='entry.description')
    amount = money(source='entry.amount')
    due_date = serializers.DateField(source='entry.due_date', allow_null=True)
    gl_account_code = serializers.CharField(source='entry.gl_account_code')
    gl_account_name = serializers.CharField(source='entry.gl_account_name')
    location = serializers.CharField(source='entry.location')
    applies_to = serializers.JSONField(source='entry.applies_to')
    running_balance = money()


class LedgerSerializer(serializers.Serializer):
    vendor = VendorSummarySerializer()
    start = serializers.DateField(allow_null=True)
    end = serializers.DateField(allow_null=True)
    opening_balance = money()
    total_invoiced = money()
    total_credits = money()
    total_paid = money()
    balance = money()
    lines = LedgerLineSerializer(many=True)
    removed_entries = LedgerEntrySerializer(many=True)
