from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import render
from .models import Customer, Raffle, Ticket, TicketTemplate, SiteSettings, SocialLink, DolibarrIntegration

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
    list_display = ('first_name', 'identification', 'phone', 'address', 'created_at')
    search_fields = ('first_name', 'phone', 'identification', 'ticket__ticket_number')
    list_filter = ('created_at',)

class SocialLinkInline(admin.TabularInline):
    model = SocialLink
    extra = 1

@admin.register(Raffle)
class RaffleAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'ticket_template', 'created_at')
    search_fields = ('name', 'year')
    list_filter = ('year', 'created_at', 'ticket_template')
    autocomplete_fields = ('ticket_template',)
    inlines = [SocialLinkInline]

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'raffle', 'customer', 'price', 'sold_at', 'view_ticket_link')
    search_fields = ('customer__first_name', 'customer__identification', 'raffle__name', 'ticket_number')
    list_filter = ('raffle', 'sold_at')
    autocomplete_fields = ('raffle', 'customer')
    actions = ['download_selected_tickets']

    def view_ticket_link(self, obj):
        url = reverse('raffles:generate_ticket', args=[obj.id])
        return format_html('<a href="{}" target="_blank" class="button">Ver Boleto</a>', url)
    view_ticket_link.short_description = "Boleto"

    def download_selected_tickets(self, request, queryset):
        """
        Action to render the bulk download page for selected tickets.
        """
        # Prefetch related data to avoid N+1 queries during rendering
        tickets = queryset.select_related('raffle', 'customer', 'raffle__ticket_template')

        # We need to make sure we pass the correct context.
        # The template loop expects 'ticket' and we pass 'ticket.raffle.ticket_template' there.

        context = {
            'tickets': tickets,
            'title': f'Descarga masiva de {tickets.count()} boletos',
        }

        return render(request, 'raffles/bulk_tickets.html', context)

    download_selected_tickets.short_description = "Descargar boletos seleccionados (PDF Masivo)"

@admin.register(DolibarrIntegration)
class DolibarrIntegrationAdmin(admin.ModelAdmin):
    list_display = ('is_active', 'tickets_per_amount', 'amount_step', 'active_raffle')
    readonly_fields = ('api_key',)

    def has_add_permission(self, request):
        # Implement Singleton: only allow add if no instance exists
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)
