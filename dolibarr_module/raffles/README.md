# Módulo de Integración Rifas - Dolibarr

Este módulo permite integrar Dolibarr con el Sistema de Rifas, enviando automáticamente información de facturas validadas para generar boletos.

## ⚠️ IMPORTANTE: Actualización (Si ya tienes una versión anterior)

Si estás actualizando desde una versión previa, **DEBES eliminar el archivo antiguo del trigger** para evitar conflictos y errores críticos.

1.  Ve a la carpeta de triggers de tu instalación: `htdocs/custom/raffles/core/triggers/` (o `htdocs/raffles/core/triggers/`).
2.  **Elimina** el archivo: `interface_50_modRaffles_RafflesTrigger.class.php`.
    - La nueva versión usa `interface_20_...`. Si no borras el `50`, tendrás dos triggers ejecutándose y el sistema fallará.
3.  Después de actualizar los archivos, se recomienda **reiniciar el servicio web** (Apache/Nginx) para limpiar la caché de PHP (OPcache):
    - `sudo systemctl restart apache2` o `sudo service apache2 restart`

## Instalación

1.  **Descargar el módulo:**
    - Si tienes el archivo `raffles_module.zip`, descomprímelo.
    - Obtendrás una carpeta llamada `raffles`.

2.  **Copiar al servidor Dolibarr:**
    - Copia la carpeta `raffles` dentro del directorio `htdocs` o `htdocs/custom` de tu instalación de Dolibarr.
    - Ejemplo: `/var/www/html/dolibarr/htdocs/custom/raffles`

3.  **Activar el módulo:**
    - Ingresa a Dolibarr como administrador.
    - Ve a **Inicio** -> **Configuración** -> **Módulos/Aplicaciones**.
    - Busca el módulo **"Integración con Sistema de Rifas"** (pestaña "Interfaces con otros sistemas" o "Otros").
    - Activa el interruptor a "ON".

## Configuración

1.  Una vez activado, haz clic en el icono de configuración (engranaje) del módulo.
2.  **Raffles API URL:** Ingresa la URL completa del webhook del sistema de rifas.
    - Ejemplo: `https://tudominio.com/raffles/api/dolibarr/webhook/`
3.  **Raffles API Key:** Ingresa la API Key generada en el sistema de rifas (Admin -> Integración Dolibarr).
4.  Guarda los cambios.

## Uso

El módulo funciona automáticamente mediante Triggers.
Cuando valides una factura de cliente (`BILL_VALIDATE`), el módulo enviará los datos al sistema de rifas.

Puedes verificar el funcionamiento en los logs de Dolibarr (si están activados) o revisando si se generan los clientes y boletos en el sistema de rifas.
