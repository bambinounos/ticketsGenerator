from django.contrib import admin
from .models import Customer, Raffle, Ticket, TicketTemplate, SiteSettings

admin.site.site_header = "Administración de Rifas"
admin.site.site_title = "Portal de Administración de Rifas"
admin.site.index_title = "Bienvenido al Portal de Administración de Rifas"


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketTemplate)
class TicketTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'background_color', 'font_color', 'created_at')
    search_fields = ('name',)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'phone', 'address', 'created_at')
    search_fields = ('first_name', 'phone')
    list_filter = ('created_at',)

@admin.register(Raffle)
class RaffleAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'ticket_template', 'created_at')
    search_fields = ('name', 'year')
    list_filter = ('year', 'created_at', 'ticket_template')
    autocomplete_fields = ('ticket_template',)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'raffle', 'customer', 'price', 'sold_at')
    search_fields = ('customer__first_name', 'raffle__name', 'ticket_number')
    list_filter = ('raffle', 'sold_at')
    autocomplete_fields = ('raffle', 'customer')
