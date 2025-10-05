from django.urls import path
from . import views

app_name = 'raffles'

urlpatterns = [
    path('ticket/<int:ticket_id>/', views.generate_ticket, name='generate_ticket'),
]