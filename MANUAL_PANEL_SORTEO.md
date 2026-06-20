# Manual de Uso del Panel de Sorteo

Guía operativa para ejecutar rifas con el panel introducido en el servidor v1.2.0.

## A quién está dirigido

A los usuarios **staff** del Django admin que realizan el sorteo, contactan a los ganadores y registran descartes. No es público.

## Antes del primer sorteo (configuración inicial)

### 1. Configurar las instancias Dolibarr

Cada Dolibarr conectada debe estar registrada como `DolibarrInstance` en Django.

1. Entrar a `/admin/raffles/dolibarrinstance/` → **Agregar Instancia Dolibarr**.
2. Llenar:
   - **Nombre**: ej. `Hellbam ERP`.
   - **Slug**: se autocompleta a partir del nombre, ej. `hellbam`.
   - **Activa**: ✅
   - **API Key (entrante)**: la clave que el módulo Raffles de **esa** Dolibarr enviará en el header `Authorization`. Debe ser **única por instancia**: si Hellbam y Kama comparten la misma, las facturas con el mismo `ref` o `facture_id` colisionan. Generar con:
     ```bash
     openssl rand -hex 32
     ```
     y pegar el resultado en este campo **y** en el setup del módulo Raffles de la Dolibarr correspondiente.
   - **URL REST API (saliente)**: URL base del API de esa Dolibarr, ej. `https://erp.hellbam.com/api/index.php`.
   - **DOLAPIKEY (saliente)**: token de un usuario Dolibarr con permisos de **lectura sobre invoices**. Se genera en cada Dolibarr: Setup → Usuarios → seleccionar usuario → pestaña API tokens → copiar el token.
   - **Política de boletos**: `tickets_per_amount` y `amount_step` (lo que antes vivía en `DolibarrIntegration`).
3. Guardar. Repetir por cada Dolibarr conectada.

> Si deja vacíos los campos salientes (URL + DOLAPIKEY), los boletos de esa instancia aparecen con el badge ⚠️ **"pago no verificado"** en el panel. No rompe nada, pero el filtro automático de impagos no puede excluirlos.

### 2. Crear o marcar la rifa activa

Solo puede haber **una rifa activa por vez** (constraint a nivel de base de datos).

1. Entrar a `/admin/raffles/raffle/`.
2. Editar la rifa que recibirá los próximos boletos → marcar **"Rifa Activa"** ✅ → guardar.
3. Si intenta marcar una segunda, la base de datos rechaza el guardado con error de constraint `only_one_active_raffle`. Desmarque la anterior primero.

### 3. Cargar los premios

Cada rifa tiene N premios fijos (1°, 2°, 3°…). Sin premios cargados, el panel muestra una advertencia y no permite sortear.

1. En la pantalla de edición de la rifa, ir a la sección **Premios** (inline).
2. Por cada premio:
   - **Posición**: 1, 2, 3…
   - **Nombre del Premio**: ej. `Auto 0km`, `Smart TV 55"`.
   - **Descripción** (opcional).
   - **Imagen** (opcional).
3. **No tocar** los campos `Boleto Ganador Actual` ni `Sorteado el`. Los maneja el panel de sorteo.
4. Guardar.

---

## Flujo de sorteo

### Abrir el panel

Dos rutas equivalentes:

- **Desde el admin**: `/admin/raffles/raffle/` → columna **Panel de Sorteo** → click **🎲 Sortear** en la fila de la rifa.
- **URL directa**: `/raffles/<id-de-la-rifa>/draw/`.

Si no está autenticado como staff, Django redirige al login.

### Lo que se ve en el panel

- **Header**: nombre de la rifa, año, link a la lista de ganadores actuales y al edit del admin, botón **🔄 Refrescar verificación de pagos**.
- **Pool elegible**: contador total + cuántos están con factura pagada (verde) + cuántos no verificados (amarillo). Debajo, la distribución por instancia (`hellbam · 42`, `kama · 18`, etc.).
- **Una card por premio**, ordenadas por posición:
  - **Sin sortear**: borde naranja + botón **🎲 Sortear**.
  - **Con ganador**: borde verde + número de boleto + cliente + teléfono + email + chip de instancia (`Hellbam ERP`) + badge de pago (verde "Factura pagada" / rojo "Factura impaga" / amarillo "Pago no verificado") + botón **🗑️ Descartar**.

### Toggle "Excluir impagos"

Junto al pool elegible hay un switch **"Excluir impagos del pool"**:

- **Activado (default)**: solo entran al sorteo los boletos con factura confirmada como pagada en Dolibarr. Los impagos y los no verificados quedan fuera.
- **Desactivado**: el sorteo elige entre **todos** los boletos del pool sin verificar pagos. Útil cuando Dolibarr está caído, o cuando la rifa es anterior a v1.2.0 y los boletos no tienen vínculo automático con Dolibarr (ver sección "Rifas pre-v1.2.0" más abajo).

Cuando el toggle está desactivado, aparece un aviso ámbar en el header que recuerda que la verificación es manual.

### Ejecutar el sorteo de un premio

1. Click en **🎲 Sortear** de la card del premio.
2. Aparece un overlay a pantalla completa con un número grande rotando aleatoriamente durante unos 2.5 segundos.
3. Cuando frena, revela el ganador real: número de boleto, nombre del cliente, teléfono, email, instancia de origen.
4. Click **Continuar** para volver al panel. La página se recarga y la card muestra al ganador definitivo.

> El sorteo usa `secrets.choice` de Python (CSPRNG criptográficamente seguro, no el Mersenne Twister del módulo `random`). El código es auditable en `raffles/views.py`.

### Qué excluye el sorteo automáticamente

El backend NUNCA puede elegir un boleto que:
- ya sea ganador en otro premio de la misma rifa,
- tenga al menos un registro de `WinnerDiscard` en cualquier premio de la misma rifa,
- tenga la factura impaga en Dolibarr (cuando el toggle "Excluir impagos" está activo, default ON).

Si el pool elegible queda en cero (típico cuando Dolibarr está caído y todos los boletos quedan "no verificado"), el sorteo responde con error y un mensaje explicando por qué.

### Descartar a un ganador

Cuando el ganador no responde, su factura no está pagada, o renuncia voluntariamente:

1. Click **🗑️ Descartar** en la card del premio.
2. Aparece un modal:
   - **Motivo** (obligatorio): `Factura impaga` / `No contactado` / `Renuncia voluntaria` / `Otro`.
   - **Notas** (opcional): detalle libre — fechas de llamadas intentadas, observaciones del cliente, etc.
3. Confirmar.

Qué pasa internamente:
- Se crea un registro `WinnerDiscard` con motivo, notas, usuario y fecha/hora.
- `Prize.winning_ticket` queda en `NULL` (vuelve a "Sin sortear").
- El boleto descartado queda fuera del pool elegible **para siempre** en esa rifa (no vuelve a salir aunque se resortee cien veces).
- Después de cerrar el modal, vuelva a hacer click en **🎲 Sortear** para elegir un nuevo ganador.

### Refrescar el estado de pago

El estado de cada factura se cachea por 10 minutos para no saturar Dolibarr. Si acaba de marcar una factura como pagada en Dolibarr y quiere que el panel lo refleje de inmediato:

- Click **🔄 Refrescar verificación de pagos** en el header.

Esto fuerza al backend a re-consultar el API REST de cada Dolibarr e invalidar la cache.

---

## Lista de ganadores

Para revisar todos los ganadores actuales de una rifa con sus datos de contacto:

- Link desde el panel: **"Ver ganadores actuales"** en el header.
- URL directa: `/raffles/<id-de-la-rifa>/winners/`.

La tabla muestra: posición, nombre del premio, número de boleto, nombre del cliente, teléfono, email, instancia de origen, estado de factura, fecha del sorteo. Está pensada para usar mientras se llama a los ganadores.

---

## Rifas pre-v1.2.0 (caso: Rifa del Día del Padre)

Las rifas cuyos boletos se generaron **antes** del servidor v1.2.0 tienen una limitación: sus boletos no tienen el vínculo `Ticket.dolibarr_transaction` poblado, porque ese campo no existía. Esto causa que:

- En el panel aparezcan con chip **"Manual"** y badge **"Pago no verificado"**.
- El filtro automático de impagos no puede excluirlos (no sabe a qué Dolibarr consultar).
- La verificación de pagos sigue funcionando para los boletos **nuevos** (los que entren desde v1.2.0 en adelante), pero no para los pre-migración.

Hay dos opciones para manejarlas:

### Opción A: Backfill automático (recomendado)

Existe un comando que intenta vincular retroactivamente cada boleto huérfano con su `DolibarrTransaction` de origen, usando proximidad temporal (los N boletos de una factura tienen `sold_at` muy cercano al `created_at` de su transacción).

**Modo simulación** (no escribe nada):
```bash
python manage.py backfill_legacy_tickets --dry-run
```

**Aplicar a toda la base**:
```bash
python manage.py backfill_legacy_tickets
```

**Aplicar solo a una rifa específica** (recomendado para la Rifa del Día del Padre):
```bash
# Primero ver el ID de la rifa en /admin/raffles/raffle/
python manage.py backfill_legacy_tickets --raffle 5 --dry-run
python manage.py backfill_legacy_tickets --raffle 5
```

**Ajustar la ventana temporal** si la heurística no encuentra matches (default 60 s):
```bash
python manage.py backfill_legacy_tickets --raffle 5 --window 300
```

Después del backfill, los boletos vinculados muestran su chip de instancia correcto y el badge de pago se calcula con la API REST de Dolibarr.

> **Limitaciones del backfill**:
> - Boletos cargados a mano por el admin (sin webhook) no tienen `DolibarrTransaction` que matchear → quedan como "Manual" para siempre.
> - Si el `DolibarrTransaction` original fue creado pero la cantidad de boletos no coincide (raro), no se vinculan.
> - La heurística depende del orden temporal: si dos clientes recibieron boletos en la misma ventana de 60 s, el comando intenta separarlos por `customer`, pero en casos extraños puede no matchear.

### Opción B: Sorteo con verificación manual

Si el backfill no es viable o no quiere usarlo, ejecute el sorteo con el toggle **"Excluir impagos"** desactivado y verifique cada ganador a mano:

1. Abrir el panel de la rifa.
2. Desactivar el switch **"Excluir impagos del pool"** (aparece un aviso ámbar).
3. Sortear cada premio normalmente.
4. Por cada ganador:
   - Abrir Dolibarr → buscar la factura del cliente.
   - Si la factura **está pagada**: contactar al ganador. Listo.
   - Si la factura **NO está pagada**: en el panel, click **🗑️ Descartar** con motivo **"Factura impaga"** → resortear.

Este flujo es más lento pero no requiere correr ningún comando ni asumir que la heurística del backfill funcionó bien. Recomendado si la rifa es importante y prefiere control manual.

### Flujo recomendado para la Rifa del Día del Padre

1. Hacer una copia de seguridad de la base de datos (medida de prudencia).
2. Probar el backfill en modo dry-run sobre esa rifa específica:
   ```bash
   python manage.py backfill_legacy_tickets --raffle <id> --dry-run
   ```
3. Revisar el reporte. Si el porcentaje de matches es razonable (por ejemplo, ≥80% de las transactions matchean), aplicar:
   ```bash
   python manage.py backfill_legacy_tickets --raffle <id>
   ```
4. Abrir el panel de la rifa, revisar que los chips de instancia aparezcan correctamente en una muestra de boletos.
5. Sortear con el toggle "Excluir impagos" **activado**.
6. Para los boletos que aún queden como "Manual" (los que no matchearon), si alguno sale ganador: verificar el pago a mano en Dolibarr antes de declararlo definitivo. Si no está pagado, descartar con motivo "Factura impaga" y resortear.

---

## Auditoría e historial

### Historial de descartes

En cada card del panel, si el premio tiene descartes previos sin un ganador definitivo todavía, aparece un elemento colapsable: **"N descarte(s) previos"**. Al expandirlo se ven los boletos que pasaron por ahí, con qué motivo y qué usuario los descartó.

### Vista completa de descartes

Para ver el historial completo de descartes de todas las rifas:

- Admin → **Descartes de Ganadores** (`/admin/raffles/winnerdiscard/`).
- Es read-only: nadie puede borrar ni editar un descarte una vez creado.
- Filtrable por motivo, rifa y fecha.

---

## Resolución de problemas

### El panel muestra "Pool elegible: 0"

Causas comunes:

1. **No hay boletos en la rifa todavía** → revisar que el webhook Dolibarr esté llegando (Admin → Transacciones Dolibarr) y que las facturas que dispararon `BILL_VALIDATE` superen el `amount_step` mínimo configurado en la instancia.
2. **Todos los boletos están en "no verificado"** → Dolibarr está caído o sin credenciales salientes configuradas. Soluciones:
   - Verificar que `DolibarrInstance.outbound_api_url` y `DolibarrInstance.outbound_api_key` estén cargados correctamente.
   - Probar manualmente: `curl -H "DOLAPIKEY: <token>" https://erp.empresa.com/api/index.php/invoices/<id>`.
   - **Alternativa**: desactivar el toggle "Excluir impagos del pool" y sortear igual (ver sección "Rifas pre-v1.2.0").

### Un boleto que ya pagó sigue saliendo en amarillo

Causas:

1. **La cache no expiró**: hacer click en **🔄 Refrescar verificación de pagos**.
2. **El boleto no está vinculado a una `DolibarrTransaction`**: pasa con boletos creados a mano (no vía webhook) o con boletos pre-migración. El badge correcto en ese caso es **"Manual"** + **"no verificado"**, y no hay forma automática de saber si la factura existe. Ver sección "Rifas pre-v1.2.0" para el comando de backfill.
3. **La instancia no tiene credenciales salientes**: configurar `outbound_api_url` y `outbound_api_key` en la `DolibarrInstance`.

### Error "Este premio ya tiene un ganador"

Pasa cuando dos pestañas o dos personas del staff sortean el mismo premio en paralelo. El segundo en confirmar recibe este error. Solución: refrescar la página, ver al ganador que quedó, y decidir si descartarlo y resortear.

### Error "Solo una rifa activa por vez"

Pasa al guardar una rifa con `is_active=True` cuando ya hay otra activa. Solución: desmarcar la otra primero.

### El historial de descartes está vacío después de muchos descartes

Solo se ve historial en cards **sin ganador definitivo**. Una vez que la card queda con ganador estable, los descartes pasados de ese premio quedan accesibles en `/admin/raffles/winnerdiscard/?prize__raffle__id__exact=<id>`.

---

## Roles y permisos

- **Cualquier usuario `is_staff=True`** puede entrar al panel, sortear y descartar.
- **Cualquier acción de descarte** registra `discarded_by` (el usuario que la ejecutó) para auditoría.
- **Superuser** no es necesario, el rol de staff alcanza.

Si quiere restringir más (por ejemplo, que solo el superuser pueda sortear), reemplace `@staff_member_required` por `@user_passes_test(lambda u: u.is_superuser)` en `raffles/views.py` (cambio futuro).

---

## Consideraciones de aleatoriedad

- El sorteo usa `secrets.choice` del stdlib de Python, que internamente usa `os.urandom()` (CSPRNG criptográficamente seguro).
- **No** usa `random.choice` (Mersenne Twister, predecible si se conoce la semilla).
- El pool elegible se construye fresco en cada llamada, no se cachea entre clicks de "Sortear".
- Hay `select_for_update()` sobre el premio dentro de una transacción atómica para evitar race conditions si dos personas del staff sortean el mismo premio simultáneamente.

Si necesita demostrar la aleatoriedad ante un notario o cliente externo, el código relevante está en `raffles/views.py`, función `execute_prize_draw`.
