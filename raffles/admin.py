from django.contrib import admin
from .models import Customer, Raffle, Ticket

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'phone', 'address', 'created_at')
    search_fields = ('first_name', 'phone')
    list_filter = ('created_at',)

@admin.register(Raffle)
class RaffleAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'created_at')
    search_fields = ('name', 'year')
    list_filter = ('year', 'created_at')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'raffle', 'customer', 'price', 'sold_at')
    search_fields = ('customer__first_name', 'raffle__name', 'ticket_number')
    list_filter = ('raffle', 'sold_at')
    autocomplete_fields = ('raffle', 'customer')
