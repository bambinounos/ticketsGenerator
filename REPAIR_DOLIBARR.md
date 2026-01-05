# Guía de Reparación de Dolibarr (Error 500 / Pantalla Blanca)

Si su instalación de Dolibarr ha dejado de funcionar (error 500 o pantalla blanca) tras intentar configurar el módulo `raffles`, siga estos pasos para recuperar el acceso.

El problema es causado por un archivo "trigger" que intenta acceder a una configuración que aún no existe, provocando un error fatal.

## Solución Rápida (Recuperar Acceso)

Para que Dolibarr vuelva a funcionar inmediatamente, debe eliminar o renombrar el archivo del trigger problemático.

### Paso 1: Acceder al Servidor
Utilice su cliente FTP (como FileZilla) o SSH para acceder a los archivos de su servidor Dolibarr.

### Paso 2: Localizar el Archivo
Navegue hasta la carpeta donde instaló el módulo. La ruta suele ser:

`.../htdocs/custom/raffles/core/triggers/`

O si lo instaló en la carpeta principal de módulos:

`.../htdocs/raffles/core/triggers/`

### Paso 3: Eliminar o Renombrar el Archivo
Busque el archivo llamado:
**`interface_20_modRaffles_RafflesTrigger.class.php`** (anteriormente `interface_50_...`)

Puede:
1. **Eliminarlo** (esto desactivará la integración temporalmente pero recuperará el sistema).
2. **Renombrarlo** a `interface_20_modRaffles_RafflesTrigger.class.php.bak` (Dolibarr ignorará archivos que no terminen en .php).

Una vez hecho esto, **intente acceder a su Dolibarr de nuevo**. Debería funcionar correctamente.

---

## Solución Definitiva (Aplicar el Parche)

Una vez haya recuperado el acceso, puede aplicar la corrección definitiva descargando la última versión del código de este repositorio o editando los archivos manualmente.

### Corrección Manual
Si desea editar los archivos manualmente:

1. **Editar `raffles/core/triggers/interface_20_modRaffles_RafflesTrigger.class.php`**:
   Busque la línea (alrededor de la línea 35):
   ```php
   if (empty($conf->raffles->enabled)) return 0;
   ```
   Y cámbiela por:
   ```php
   if (!isset($conf->raffles) || empty($conf->raffles->enabled)) return 0;
   ```

2. **Editar `raffles/admin/setup.php`**:
   Busque la línea (alrededor de la línea 25):
   ```php
   global $langs, $user;
   ```
   Y cámbiela por:
   ```php
   global $langs, $user, $conf;
   ```
