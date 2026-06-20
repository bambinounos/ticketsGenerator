import uuid
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q, UniqueConstraint
from django.utils import timezone

class Customer(models.Model):
    """Modelo para almacenar los datos del cliente."""
    first_name = models.CharField(max_length=100, verbose_name="Nombres")
    identification = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Cédula/RUC/Pasaporte")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    additional_info = models.TextField(blank=True, null=True, verbose_name="Información Adicional")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def save(self, *args, **kwargs):
        if self.identification == "":
            self.identification = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} - {self.phone or 'Sin teléfono'}"

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"


class TicketTemplate(models.Model):
    """Modelo para plantillas de boletos."""
    name = models.CharField(max_length=100, verbose_name="Nombre de la Plantilla")
    background_color = models.CharField(max_length=7, default="#FFFFFF", verbose_name="Color de Fondo")
    font_color = models.CharField(max_length=7, default="#000000", verbose_name="Color de la Fuente")
    background_image = models.ImageField(upload_to='ticket_backgrounds/', blank=True, null=True, verbose_name="Imagen de Fondo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Plantilla de Boleto"
        verbose_name_plural = "Plantillas de Boletos"


class Raffle(models.Model):
    """Modelo para gestionar las rifas."""
    name = models.CharField(max_length=255, verbose_name="Nombre de la Rifa")
    year = models.IntegerField(
        validators=[MinValueValidator(2000)],
        default=timezone.now().year,
        verbose_name="Año"
    )
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    logo = models.ImageField(upload_to='logos/', blank=True, null=True, verbose_name="Logotipo")
    product_images = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Imágenes de Productos")
    social_links = models.TextField(blank=True, null=True, verbose_name="Links de Redes Sociales (Texto antiguo)")
    ticket_template = models.ForeignKey(
        TicketTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Plantilla de Boleto"
    )
    draw_datetime = models.DateTimeField(null=True, blank=True, verbose_name="Fecha y Hora del Sorteo")
    winning_ticket = models.ForeignKey(
        'Ticket',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_raffle',
        verbose_name="Boleto Ganador (Deprecado)",
        help_text="Campo deprecado: usar el panel de Premios para sorteos múltiples."
    )
    is_active = models.BooleanField(
        default=False,
        verbose_name="Rifa Activa",
        help_text="Sólo una rifa puede estar activa por vez (recibe boletos de los webhooks Dolibarr).",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def __str__(self):
        return f"{self.name} - {self.year}"

    class Meta:
        verbose_name = "Rifa"
        verbose_name_plural = "Rifas"
        unique_together = ('name', 'year')
        constraints = [
            UniqueConstraint(
                fields=['is_active'],
                condition=Q(is_active=True),
                name='only_one_active_raffle',
            ),
        ]


class SocialLink(models.Model):
    """Modelo para enlaces de redes sociales."""
    raffle = models.ForeignKey(
        Raffle,
        on_delete=models.CASCADE,
        related_name='social_links_list',
        verbose_name="Rifa"
    )
    platform_name = models.CharField(max_length=50, verbose_name="Nombre de la Plataforma")
    url = models.URLField(verbose_name="Enlace")
    icon = models.ImageField(upload_to='social_icons/', verbose_name="Icono", blank=True, null=True)

    def __str__(self):
        return self.platform_name

    class Meta:
        verbose_name = "Red Social"
        verbose_name_plural = "Redes Sociales"


class Ticket(models.Model):
    """Modelo para cada boleto de la rifa."""
    raffle = models.ForeignKey(Raffle, on_delete=models.CASCADE, related_name='tickets', verbose_name="Rifa")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='tickets', verbose_name="Cliente")
    ticket_number = models.PositiveIntegerField(verbose_name="Número de Boleto")
    qr_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Código QR de Verificación")
    sold_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Venta")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio")
    dolibarr_transaction = models.ForeignKey(
        'DolibarrTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name="Transacción Dolibarr de origen",
    )

    def __str__(self):
        return f"Boleto N° {self.ticket_number} - {self.raffle.name}"

    class Meta:
        verbose_name = "Boleto"
        verbose_name_plural = "Boletos"
        unique_together = ('raffle', 'ticket_number')


class SiteSettings(models.Model):
    """Modelo para la configuración del sitio."""
    favicon = models.ImageField(upload_to='favicons/', blank=True, null=True, verbose_name="Favicon")

    def __str__(self):
        return "Configuración del Sitio"

    class Meta:
        verbose_name = "Configuración del Sitio"
        verbose_name_plural = "Configuración del Sitio"


class DolibarrIntegration(models.Model):
    """Deprecated singleton config — kept for rollback safety. Use DolibarrInstance."""
    api_key = models.CharField(max_length=64, default=uuid.uuid4, unique=True, verbose_name="API Key", help_text="Secret key to validate requests from Dolibarr")
    active_raffle = models.ForeignKey(Raffle, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Rifa Activa")
    tickets_per_amount = models.PositiveIntegerField(default=1, verbose_name="Boletos por Monto")
    amount_step = models.DecimalField(max_digits=10, decimal_places=2, default=100.00, verbose_name="Monto Base ($)")
    is_active = models.BooleanField(default=False, verbose_name="Integración Activa")
    default_ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio del Boleto (Registro)")

    def __str__(self):
        return "Configuración Dolibarr (Deprecada)"

    class Meta:
        verbose_name = "Integración Dolibarr (Deprecada)"
        verbose_name_plural = "Integración Dolibarr (Deprecada)"


class DolibarrInstance(models.Model):
    """One row per Dolibarr installation that talks to this Django app."""
    name = models.CharField(max_length=80, verbose_name="Nombre de la Instancia")
    slug = models.SlugField(unique=True, verbose_name="Slug")
    inbound_api_key = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="API Key (entrante)",
        help_text="Clave que el módulo Raffles de esta instancia Dolibarr envía en Authorization.",
    )
    outbound_api_url = models.URLField(
        blank=True,
        verbose_name="URL REST API (saliente)",
        help_text="Base URL de la API REST de Dolibarr, ej. https://erp.empresa.com/api/index.php",
    )
    outbound_api_key = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="DOLAPIKEY (saliente)",
        help_text="Token del usuario API para consultar facturas (lectura de invoices).",
    )
    tickets_per_amount = models.PositiveIntegerField(default=1, verbose_name="Boletos por Monto")
    amount_step = models.DecimalField(max_digits=10, decimal_places=2, default=100.00, verbose_name="Monto Base ($)")
    default_ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio del Boleto (Registro)")
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Instancia Dolibarr"
        verbose_name_plural = "Instancias Dolibarr"
        ordering = ['name']


class DolibarrTransaction(models.Model):
    """Log of processed Dolibarr transactions to ensure idempotency (per instance)."""
    instance = models.ForeignKey(
        DolibarrInstance,
        on_delete=models.PROTECT,
        related_name='transactions',
        null=True,
        blank=True,
        verbose_name="Instancia Dolibarr",
    )
    ref = models.CharField(max_length=100, verbose_name="Referencia Dolibarr (Factura/Pedido)")
    facture_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="ID Factura Dolibarr", help_text="ID interno de la factura en Dolibarr (no cambia al re-validar)")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto")
    tickets_count = models.IntegerField(verbose_name="Boletos Generados")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        prefix = f"[{self.instance.slug}] " if self.instance_id else ""
        return f"{prefix}{self.ref}"

    class Meta:
        verbose_name = "Transacción Dolibarr"
        verbose_name_plural = "Transacciones Dolibarr"
        constraints = [
            UniqueConstraint(fields=['instance', 'ref'], name='uniq_instance_ref'),
            UniqueConstraint(
                fields=['instance', 'facture_id'],
                condition=Q(facture_id__isnull=False),
                name='uniq_instance_facture_id',
            ),
        ]


class Prize(models.Model):
    """One prize slot inside a Raffle (1°, 2°, 3°...). Holds the current winner."""
    raffle = models.ForeignKey(Raffle, on_delete=models.CASCADE, related_name='prizes', verbose_name="Rifa")
    position = models.PositiveIntegerField(verbose_name="Posición")
    name = models.CharField(max_length=200, verbose_name="Nombre del Premio")
    description = models.TextField(blank=True, verbose_name="Descripción")
    image = models.ImageField(upload_to='prizes/', blank=True, null=True, verbose_name="Imagen")
    winning_ticket = models.ForeignKey(
        Ticket,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Boleto Ganador Actual",
    )
    drawn_at = models.DateTimeField(null=True, blank=True, verbose_name="Sorteado el")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"#{self.position} {self.name} ({self.raffle.name})"

    class Meta:
        verbose_name = "Premio"
        verbose_name_plural = "Premios"
        unique_together = ('raffle', 'position')
        ordering = ['raffle', 'position']


class WinnerDiscard(models.Model):
    """Audit trail of every winner removed from a Prize before the final one sticks."""
    class Reason(models.TextChoices):
        UNPAID_INVOICE = 'unpaid_invoice', 'Factura impaga'
        NO_CONTACT = 'no_contact', 'No contactado'
        VOLUNTARY = 'voluntary', 'Renuncia voluntaria'
        OTHER = 'other', 'Otro'

    prize = models.ForeignKey(Prize, on_delete=models.CASCADE, related_name='discards', verbose_name="Premio")
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='discards', verbose_name="Boleto Descartado")
    reason = models.CharField(max_length=32, choices=Reason.choices, verbose_name="Motivo")
    notes = models.TextField(blank=True, verbose_name="Notas")
    discarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Descartado por",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prize} → {self.ticket} ({self.get_reason_display()})"

    class Meta:
        verbose_name = "Descarte de Ganador"
        verbose_name_plural = "Descartes de Ganadores"
        ordering = ['-created_at']
