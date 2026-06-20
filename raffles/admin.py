from django.contrib import admin
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Customer,
    DolibarrIntegration,
    DolibarrInstance,
    DolibarrTransaction,
    Prize,
    Raffle,
    SiteSettings,
    SocialLink,
    Ticket,
    TicketTemplate,
    WinnerDiscard,
)
from .version import __version__

admin.site.site_header = f"Administración de Rifas v{__version__}"
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


class PrizeInline(admin.TabularInline):
    model = Prize
    extra = 1
    fields = ('position', 'name', 'description', 'image', 'winning_ticket', 'drawn_at')
    readonly_fields = ('drawn_at',)
    autocomplete_fields = ('winning_ticket',)
    ordering = ('position',)


@admin.register(Raffle)
class RaffleAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'is_active', 'ticket_template', 'created_at', 'draw_link')
    search_fields = ('name', 'year')
    list_filter = ('is_active', 'year', 'created_at', 'ticket_template')
    autocomplete_fields = ('ticket_template',)
    inlines = [PrizeInline, SocialLinkInline]

    def draw_link(self, obj):
        url = reverse('raffles:raffle_draw_dashboard', args=[obj.id])
        return format_html('<a href="{}" class="button" style="font-weight:700">🎲 Sortear</a>', url)
    draw_link.short_description = "Panel de Sorteo"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'raffle', 'customer', 'price', 'sold_at', 'instance_chip', 'view_ticket_link')
    search_fields = ('customer__first_name', 'customer__identification', 'raffle__name', 'ticket_number')
    list_filter = ('raffle', 'sold_at', 'dolibarr_transaction__instance')
    autocomplete_fields = ('raffle', 'customer', 'dolibarr_transaction')
    actions = ['download_selected_tickets']

    def view_ticket_link(self, obj):
        url = reverse('raffles:generate_ticket', args=[obj.id])
        return format_html('<a href="{}" target="_blank" class="button">Ver Boleto</a>', url)
    view_ticket_link.short_description = "Boleto"

    def instance_chip(self, obj):
        if obj.dolibarr_transaction_id and obj.dolibarr_transaction.instance_id:
            return obj.dolibarr_transaction.instance.name
        return "Manual"
    instance_chip.short_description = "Instancia"

    def download_selected_tickets(self, request, queryset):
        tickets = queryset.select_related('raffle', 'customer', 'raffle__ticket_template')
        context = {
            'tickets': tickets,
            'title': f'Descarga masiva de {tickets.count()} boletos',
        }
        return render(request, 'raffles/bulk_tickets.html', context)

    download_selected_tickets.short_description = "Descargar boletos seleccionados (PDF Masivo)"


@admin.register(DolibarrInstance)
class DolibarrInstanceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'tickets_per_amount', 'amount_step', 'outbound_api_url', 'created_at')
    search_fields = ('name', 'slug')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'is_active'),
        }),
        ('Credenciales entrantes (recibidas del módulo Dolibarr)', {
            'fields': ('inbound_api_key',),
            'description': 'La key que el módulo Raffles de esta Dolibarr envía en el header Authorization. Debe ser única por instancia para evitar colisiones de facture_id entre empresas.',
        }),
        ('Credenciales salientes (para consultar pagos)', {
            'fields': ('outbound_api_url', 'outbound_api_key'),
            'description': 'Necesarias para que el panel de sorteo pueda verificar el estado de pago de cada factura contra esta Dolibarr.',
        }),
        ('Política de boletos', {
            'fields': ('tickets_per_amount', 'amount_step', 'default_ticket_price'),
        }),
    )


@admin.register(DolibarrTransaction)
class DolibarrTransactionAdmin(admin.ModelAdmin):
    list_display = ('instance', 'ref', 'facture_id', 'amount', 'tickets_count', 'created_at')
    search_fields = ('ref', 'facture_id')
    list_filter = ('instance', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('instance',)


@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = ('raffle', 'position', 'name', 'winning_ticket', 'drawn_at')
    list_filter = ('raffle',)
    search_fields = ('name', 'raffle__name')
    autocomplete_fields = ('raffle', 'winning_ticket')
    readonly_fields = ('drawn_at',)


@admin.register(WinnerDiscard)
class WinnerDiscardAdmin(admin.ModelAdmin):
    list_display = ('prize', 'ticket', 'reason', 'discarded_by', 'created_at')
    list_filter = ('reason', 'prize__raffle', 'created_at')
    search_fields = ('prize__name', 'ticket__ticket_number', 'notes')
    readonly_fields = ('prize', 'ticket', 'reason', 'notes', 'discarded_by', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DolibarrIntegration)
class DolibarrIntegrationAdmin(admin.ModelAdmin):
    """Read-only view of the legacy singleton. Kept for rollback safety; use
    DolibarrInstance for all new configuration."""
    list_display = ('is_active', 'tickets_per_amount', 'amount_step', 'active_raffle')
    readonly_fields = ('api_key', 'active_raffle', 'tickets_per_amount', 'amount_step', 'is_active', 'default_ticket_price')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        # Force read-only on existing rows.
        return False
