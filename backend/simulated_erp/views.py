"""A stand-in for the customer's ERP (accounting system) integration API.

It serves a fixed JSON file so the exercise runs offline and every run sees the
same data. Treat it as an external system: the app reads from it through the
importer and never writes to it. See API_SPEC.md.
"""
import json
from pathlib import Path

from rest_framework.decorators import api_view
from rest_framework.response import Response

DATA_FILE = Path(__file__).resolve().parent / 'data' / 'vendors.json'


def _vendors():
    # Read on every request, so edits to the file show up without a restart.
    with open(DATA_FILE, encoding='utf-8') as source:
        return json.load(source)


@api_view(['GET'])
def vendor_list(request):
    include_ledgers = request.query_params.get('includeLedgers') == 'true'
    vendors = _vendors()
    if not include_ledgers:
        vendors = [{key: value for key, value in vendor.items() if key != 'ledger'} for vendor in vendors]
    return Response(vendors)
