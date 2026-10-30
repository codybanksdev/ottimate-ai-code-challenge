from django.urls import path

from .views import ledger_entry_list, vendor_ledger, vendor_list

urlpatterns = [
    path('vendors/', vendor_list, name='vendor_list'),
    path('vendors/<int:vendor_id>/ledger/', vendor_ledger, name='vendor_ledger'),
    path('ledger-entries/', ledger_entry_list, name='ledger_entry_list'),
]
