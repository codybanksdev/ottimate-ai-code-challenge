from django.urls import include, path

from api.views import welcome_message

urlpatterns = [
    path('api/', include('api.urls')),
    path('simulated-erp-api/', include('simulated_erp.urls')),
    path('', welcome_message, name='welcome_message'),
]
