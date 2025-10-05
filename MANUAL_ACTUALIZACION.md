# Manual de Actualización del Software

Este manual describe los pasos para actualizar la aplicación de rifas cuando se realizan cambios en el código fuente del repositorio.

## Prerrequisitos

- Acceso `sudo` al servidor donde está alojada la aplicación.
- La aplicación debe haber sido instalada siguiendo el `MANUAL_PRODUCCION.md`.

## Proceso de Actualización

Sigue estos pasos para actualizar la aplicación de forma segura.

### 1. Acceder al Directorio del Proyecto

Conéctate al servidor y navega al directorio donde se encuentra el código de la aplicación.

```bash
cd /var/www/raffles
```

### 2. Poner la Aplicación en Mantenimiento (Opcional)

Si deseas mostrar una página de mantenimiento mientras actualizas, puedes hacerlo modificando la configuración de Apache para que apunte temporalmente a una página estática.

### 3. Obtener los Últimos Cambios

Descarga los cambios más recientes desde la rama principal (o la rama de producción que utilices) del repositorio.

```bash
sudo git pull origin main
```

### 4. Activar el Entorno Virtual

Activa el entorno virtual de Python para gestionar las dependencias del proyecto.

```bash
source venv/bin/activate
```

### 5. Instalar o Actualizar Dependencias

Si se han añadido o modificado librerías en el archivo `requirements.txt`, instálalas.

```bash
pip install -r requirements.txt
```

### 6. Aplicar Migraciones de la Base de Datos

Si los cambios en el código incluyen modificaciones en los modelos de Django, aplica las migraciones a la base de datos.

```bash
python manage.py migrate
```

### 7. Recolectar Archivos Estáticos

Recolecta los archivos estáticos actualizados (CSS, JavaScript, imágenes) para que Apache pueda servirlos.

```bash
python manage.py collectstatic --noinput
```

### 8. Reiniciar el Servicio de Gunicorn

Para que los cambios en el código de la aplicación surtan efecto, reinicia el servicio de Gunicorn.

```bash
sudo systemctl restart gunicorn
```

### 9. Verificar el Estado de la Aplicación

Asegúrate de que la aplicación funcione correctamente accediendo a tu dominio en un navegador.

Revisa los logs si encuentras algún problema:
- **Logs de Gunicorn:** `sudo journalctl -u gunicorn`
- **Logs de Apache:** `sudo tail -f /var/log/apache2/error.log`

### 10. Salir del Entorno Virtual

Una vez que hayas terminado, puedes desactivar el entorno virtual.

```bash
deactivate
```

Con estos pasos, tu aplicación estará actualizada y funcionando con la última versión del código.