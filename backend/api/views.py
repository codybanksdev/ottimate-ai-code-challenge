from datetime import datetime

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from api.models import LedgerEntry, Vendor
from api.serializers import LedgerEntrySerializer, LedgerSerializer, VendorSerializer
from api.services.ledger import build_ledger


@api_view(['GET'])
def welcome_message(request):
    """A simple view to test the API."""
    return Response({'message': 'Ottimate AP code challenge API. Try /api/vendors/.'})


def _date_param(request, name):
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        # strptime, not date.fromisoformat, which also accepts 20230105.
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError({name: 'Use the format YYYY-MM-DD.'})


@api_view(['GET'])
def vendor_list(request):
    """
    Returns all vendors with the balance owed to each. With `as_of`
    (YYYY-MM-DD), balances are as of the close of that day.
    """
    as_of = _date_param(request, 'as_of')
    vendors = Vendor.objects.with_balance(as_of=as_of).order_by('name', 'id')
    return Response(VendorSerializer(vendors, many=True).data)


@api_view(['GET'])
def vendor_ledger(request, vendor_id):
    """
    Returns one vendor's ledger entries, oldest first, with a running balance
    and totals. Optional `start` and `end` (YYYY-MM-DD) limit it to a period:
    earlier entries become the opening balance, and the balance returned is the
    balance as of `end`.
    """
    vendor = get_object_or_404(Vendor, pk=vendor_id)
    start = _date_param(request, 'start')
    end = _date_param(request, 'end')
    if start and end and start > end:
        raise ValidationError({'start': 'start must not be after end.'})
    return Response(LedgerSerializer(build_ledger(vendor, start=start, end=end)).data)


@api_view(['GET'])
def ledger_entry_list(request):
    """
    Returns raw ledger entries, optionally for one vendor (`?vendor=<id>`).
    """
    entries = LedgerEntry.objects.order_by('date', 'erp_id')
    vendor_id = request.query_params.get('vendor')
    if vendor_id is not None:
        if not vendor_id.isdigit():
            raise ValidationError({'vendor': 'vendor must be a vendor id.'})
        entries = entries.filter(vendor_id=vendor_id)
    return Response(LedgerEntrySerializer(entries, many=True).data)
