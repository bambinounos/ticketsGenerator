import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_instance_and_prizes(apps, schema_editor):
    """Move data from the legacy DolibarrIntegration singleton into the new
    DolibarrInstance model, link existing DolibarrTransactions to it, mark the
    currently active raffle, and convert any manually picked winning_ticket
    into a single Prize so the new draw panel still shows historical raffles."""
    DolibarrIntegration = apps.get_model('raffles', 'DolibarrIntegration')
    DolibarrInstance = apps.get_model('raffles', 'DolibarrInstance')
    DolibarrTransaction = apps.get_model('raffles', 'DolibarrTransaction')
    Raffle = apps.get_model('raffles', 'Raffle')
    Prize = apps.get_model('raffles', 'Prize')

    legacy = DolibarrIntegration.objects.first()
    default_instance = None
    if legacy is not None:
        default_instance = DolibarrInstance.objects.create(
            name="Default (migrado)",
            slug="default",
            inbound_api_key=str(legacy.api_key),
            outbound_api_url="",
            outbound_api_key="",
            tickets_per_amount=legacy.tickets_per_amount,
            amount_step=legacy.amount_step,
            default_ticket_price=legacy.default_ticket_price,
            is_active=bool(legacy.is_active),
        )
        DolibarrTransaction.objects.filter(instance__isnull=True).update(instance=default_instance)
        if legacy.active_raffle_id:
            Raffle.objects.filter(pk=legacy.active_raffle_id).update(is_active=True)

    for raffle in Raffle.objects.exclude(winning_ticket__isnull=True):
        Prize.objects.get_or_create(
            raffle=raffle,
            position=1,
            defaults={
                'name': 'Premio único',
                'description': 'Premio importado del campo legacy Raffle.winning_ticket.',
                'winning_ticket_id': raffle.winning_ticket_id,
                'drawn_at': raffle.draw_datetime,
            },
        )


def noop_reverse(apps, schema_editor):
    """Backwards migration is a no-op: data stays in the new tables."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('raffles', '0012_add_facture_id_to_dolibarr_transaction'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ---- New tables -------------------------------------------------
        migrations.CreateModel(
            name='DolibarrInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, verbose_name='Nombre de la Instancia')),
                ('slug', models.SlugField(unique=True, verbose_name='Slug')),
                ('inbound_api_key', models.CharField(help_text='Clave que el módulo Raffles de esta instancia Dolibarr envía en Authorization.', max_length=64, unique=True, verbose_name='API Key (entrante)')),
                ('outbound_api_url', models.URLField(blank=True, help_text='Base URL de la API REST de Dolibarr, ej. https://erp.empresa.com/api/index.php', verbose_name='URL REST API (saliente)')),
                ('outbound_api_key', models.CharField(blank=True, help_text='Token del usuario API para consultar facturas (lectura de invoices).', max_length=128, verbose_name='DOLAPIKEY (saliente)')),
                ('tickets_per_amount', models.PositiveIntegerField(default=1, verbose_name='Boletos por Monto')),
                ('amount_step', models.DecimalField(decimal_places=2, default=100.00, max_digits=10, verbose_name='Monto Base ($)')),
                ('default_ticket_price', models.DecimalField(decimal_places=2, default=0.00, max_digits=10, verbose_name='Precio del Boleto (Registro)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activa')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
            ],
            options={
                'verbose_name': 'Instancia Dolibarr',
                'verbose_name_plural': 'Instancias Dolibarr',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Prize',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveIntegerField(verbose_name='Posición')),
                ('name', models.CharField(max_length=200, verbose_name='Nombre del Premio')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('image', models.ImageField(blank=True, null=True, upload_to='prizes/', verbose_name='Imagen')),
                ('drawn_at', models.DateTimeField(blank=True, null=True, verbose_name='Sorteado el')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('raffle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prizes', to='raffles.raffle', verbose_name='Rifa')),
                ('winning_ticket', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='raffles.ticket', verbose_name='Boleto Ganador Actual')),
            ],
            options={
                'verbose_name': 'Premio',
                'verbose_name_plural': 'Premios',
                'ordering': ['raffle', 'position'],
                'unique_together': {('raffle', 'position')},
            },
        ),
        migrations.CreateModel(
            name='WinnerDiscard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('unpaid_invoice', 'Factura impaga'), ('no_contact', 'No contactado'), ('voluntary', 'Renuncia voluntaria'), ('other', 'Otro')], max_length=32, verbose_name='Motivo')),
                ('notes', models.TextField(blank=True, verbose_name='Notas')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('prize', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='discards', to='raffles.prize', verbose_name='Premio')),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='discards', to='raffles.ticket', verbose_name='Boleto Descartado')),
                ('discarded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Descartado por')),
            ],
            options={
                'verbose_name': 'Descarte de Ganador',
                'verbose_name_plural': 'Descartes de Ganadores',
                'ordering': ['-created_at'],
            },
        ),

        # ---- New fields on existing tables ------------------------------
        migrations.AddField(
            model_name='raffle',
            name='is_active',
            field=models.BooleanField(default=False, help_text='Sólo una rifa puede estar activa por vez (recibe boletos de los webhooks Dolibarr).', verbose_name='Rifa Activa'),
        ),
        migrations.AlterField(
            model_name='raffle',
            name='winning_ticket',
            field=models.ForeignKey(blank=True, help_text='Campo deprecado: usar el panel de Premios para sorteos múltiples.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='won_raffle', to='raffles.ticket', verbose_name='Boleto Ganador (Deprecado)'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='dolibarr_transaction',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tickets', to='raffles.dolibarrtransaction', verbose_name='Transacción Dolibarr de origen'),
        ),
        migrations.AddField(
            model_name='dolibarrtransaction',
            name='instance',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='raffles.dolibarrinstance', verbose_name='Instancia Dolibarr'),
        ),

        # ---- Backfill ---------------------------------------------------
        migrations.RunPython(backfill_instance_and_prizes, noop_reverse),

        # ---- Tighten DolibarrTransaction uniqueness after backfill -----
        migrations.AlterField(
            model_name='dolibarrtransaction',
            name='ref',
            field=models.CharField(max_length=100, verbose_name='Referencia Dolibarr (Factura/Pedido)'),
        ),
        migrations.AlterModelOptions(
            name='dolibarrtransaction',
            options={'verbose_name': 'Transacción Dolibarr', 'verbose_name_plural': 'Transacciones Dolibarr'},
        ),
        migrations.AddConstraint(
            model_name='dolibarrtransaction',
            constraint=models.UniqueConstraint(fields=('instance', 'ref'), name='uniq_instance_ref'),
        ),
        migrations.AddConstraint(
            model_name='dolibarrtransaction',
            constraint=models.UniqueConstraint(
                condition=models.Q(facture_id__isnull=False),
                fields=('instance', 'facture_id'),
                name='uniq_instance_facture_id',
            ),
        ),

        # ---- Constrain active raffle to one row at a time --------------
        migrations.AddConstraint(
            model_name='raffle',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True),
                fields=('is_active',),
                name='only_one_active_raffle',
            ),
        ),

        # ---- Deprecate the legacy singleton in admin/UI labels ---------
        migrations.AlterModelOptions(
            name='dolibarrintegration',
            options={
                'verbose_name': 'Integración Dolibarr (Deprecada)',
                'verbose_name_plural': 'Integración Dolibarr (Deprecada)',
            },
        ),
    ]
