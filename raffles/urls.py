from django.urls import path

from . import views

app_name = 'raffles'

urlpatterns = [
    path('ticket/<int:ticket_id>/', views.generate_ticket, name='generate_ticket'),
    path('verify/<uuid:qr_code>/', views.verify_ticket, name='verify_ticket'),
    path('api/dolibarr/webhook/', views.DolibarrWebhookView.as_view(), name='dolibarr_webhook'),

    # Draw panel (staff only)
    path('<int:raffle_id>/draw/', views.raffle_draw_dashboard, name='raffle_draw_dashboard'),
    path('<int:raffle_id>/prize/<int:prize_id>/draw/', views.execute_prize_draw, name='execute_prize_draw'),
    path('<int:raffle_id>/prize/<int:prize_id>/discard/', views.discard_winner, name='discard_winner'),
    path('<int:raffle_id>/winners/', views.winners_list, name='winners_list'),
]
