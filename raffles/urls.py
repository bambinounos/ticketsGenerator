
from django.urls import path
from . import views

app_name = 'raffles'

urlpatterns = [
    path('ticket/<int:ticket_id>/', views.generate_ticket, name='generate_ticket'),
    path('verify/<uuid:qr_code>/', views.verify_ticket, name='verify_ticket'),
    path('api/dolibarr/webhook/', views.DolibarrWebhookView.as_view(), name='dolibarr_webhook'),
]
