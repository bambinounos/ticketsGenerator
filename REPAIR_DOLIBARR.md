# Guía de Reparación de Dolibarr (Error 500 / Pantalla Blanca)

Si su instalación de Dolibarr ha dejado de funcionar (error 500 o pantalla blanca) tras intentar configurar el módulo `raffles`, siga estos pasos para recuperar el acceso.

El problema era causado por un archivo "trigger" que intentaba acceder a una configuración que aún no existía, provocando un error fatal. **Este problema ha sido corregido en la versión actual del módulo.**

## Solución Recomendada

La forma más sencilla de solucionar el problema es actualizar a la última versión del módulo desde este repositorio. La versión actual incluye verificaciones defensivas que previenen errores fatales incluso cuando el módulo no está completamente inicializado.

### Cambios Realizados en la Versión Actual

1. **Verificación defensiva completa**: El trigger ahora verifica que `$conf->raffles` exista antes de acceder a sus propiedades.
2. **Manejo de errores global**: Todo el método `runTrigger` está envuelto en un bloque try/catch para capturar cualquier error y evitar que afecte a otros triggers del sistema.
3. **Verificación dual de activación**: Se verifica tanto `$conf->raffles->enabled` como `$conf->global->MAIN_MODULE_RAFFLES` para mayor estabilidad.
4. **Acceso defensivo a propiedades**: Todas las propiedades del objeto se acceden de forma defensiva usando `isset()`.

## Solución Rápida (Si Necesita Recuperar Acceso Inmediato)

Si su Dolibarr está completamente bloqueado y necesita recuperar el acceso inmediatamente:

### Paso 1: Acceder al Servidor
Utilice su cliente FTP (como FileZilla) o SSH para acceder a los archivos de su servidor Dolibarr.

### Paso 2: Localizar el Archivo
Navegue hasta la carpeta donde instaló el módulo. La ruta suele ser:

`.../htdocs/custom/raffles/core/triggers/`

O si lo instaló en la carpeta principal de módulos:

`.../htdocs/raffles/core/triggers/`

### Paso 3: Eliminar o Renombrar el Archivo Temporalmente
Busque el archivo llamado:
**`interface_20_modRaffles_RafflesTrigger.class.php`**

Puede:
1. **Renombrarlo** a `interface_20_modRaffles_RafflesTrigger.class.php.bak` (Dolibarr ignorará archivos que no terminen en .php).

Una vez hecho esto, **intente acceder a su Dolibarr de nuevo**. Debería funcionar correctamente.

### Paso 4: Actualizar el Módulo
Después de recuperar el acceso, descargue la última versión del módulo desde este repositorio y reemplace los archivos antiguos.

## Compatibilidad

El módulo es compatible con:
- **Dolibarr**: Versión 14.0 o superior (probado en 17.0.4)
- **PHP**: Versión 7.0 o superior (compatible con PHP 8.x)
