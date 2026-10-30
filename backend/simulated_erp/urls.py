from django.urls import path

from .views import vendor_list

urlpatterns = [
    path('vendors/', vendor_list, name='erp_vendor_list'),
]
