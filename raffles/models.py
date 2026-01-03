import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

class Customer(models.Model):
    """Modelo para almacenar los datos del cliente."""
    first_name = models.CharField(max_length=100, verbose_name="Nombres")
    identification = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Cédula/RUC/Pasaporte")
    address = models.CharField(max_length=255, verbose_name="Dirección")
    phone = models.CharField(max_length=20, verbose_name="Teléfono")
    additional_info = models.TextField(blank=True, null=True, verbose_name="Información Adicional")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def save(self, *args, **kwargs):
        if self.identification == "":
            self.identification = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} - {self.phone}"

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
    social_links = models.TextField(blank=True, null=True, verbose_name="Links de Redes Sociales")
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
        verbose_name="Boleto Ganador"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")

    def __str__(self):
        return f"{self.name} - {self.year}"

    class Meta:
        verbose_name = "Rifa"
        verbose_name_plural = "Rifas"
        unique_together = ('name', 'year')

class Ticket(models.Model):
    """Modelo para cada boleto de la rifa."""
    raffle = models.ForeignKey(Raffle, on_delete=models.CASCADE, related_name='tickets', verbose_name="Rifa")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='tickets', verbose_name="Cliente")
    ticket_number = models.PositiveIntegerField(verbose_name="Número de Boleto")
    qr_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Código QR de Verificación")
    sold_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Venta")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio")

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
