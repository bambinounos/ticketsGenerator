# Manual de Instalación en Producción

Este manual describe los pasos para instalar y configurar la aplicación de rifas en un servidor de producción Ubuntu, utilizando Gunicorn como servidor de aplicación y Apache2 como proxy inverso.

## 1. Prerrequisitos

- Un servidor con Ubuntu 22.04 o superior.
- Acceso `sudo` al servidor.
- Git instalado (`sudo apt install git`).
- PostgreSQL instalado y en ejecución.

## 2. Instalación del Sistema

### 2.1. Clonar el Repositorio

Clona el código fuente desde el repositorio a un directorio de tu elección, por ejemplo, `/var/www/`.

```bash
sudo git clone <URL_DEL_REPOSITORIO> /var/www/raffles
cd /var/www/raffles
```

### 2.2. Instalar Paquetes del Sistema

Instala Python, el gestor de entornos virtuales y Apache2.

```bash
sudo apt update
sudo apt install python3-venv python3-pip apache2 libapache2-mod-proxy-html libxml2-dev
```

### 2.3. Crear Entorno Virtual

Crea un entorno virtual para aislar las dependencias del proyecto.

```bash
sudo python3 -m venv venv
```

Activa el entorno virtual:

```bash
source venv/bin/activate
```

**Nota:** De ahora en adelante, todos los comandos de Python (`pip`, `python`) se deben ejecutar con el entorno virtual activado.

### 2.4. Instalar Dependencias de Python

Instala las librerías necesarias usando el archivo `requirements.txt`.

```bash
pip install -r requirements.txt
```

## 3. Configuración de la Base de Datos

### 3.1. Crear Usuario y Base de Datos en PostgreSQL

Accede a la consola de PostgreSQL y crea una base de datos y un usuario para la aplicación.

```bash
sudo -u postgres psql
```

Dentro de la consola de `psql`:

```sql
CREATE DATABASE raffles_db;
CREATE USER raffles_user WITH PASSWORD 'una_contraseña_segura';
GRANT ALL PRIVILEGES ON DATABASE raffles_db TO raffles_user;
ALTER ROLE raffles_user SET client_encoding TO 'utf8';
ALTER ROLE raffles_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE raffles_user SET timezone TO 'UTC';
\q
```

## 4. Configuración de la Aplicación

### 4.1. Crear Archivo de Entorno `.env`

La aplicación utiliza un archivo `.env` para gestionar las variables de entorno. Crea este archivo en la raíz del proyecto (`/var/www/raffles/.env`).

```bash
sudo nano /var/www/raffles/.env
```

Añade el siguiente contenido, reemplazando los valores según tu configuración:

```ini
SECRET_KEY=tu_django_secret_key_aqui
DEBUG=False
DB_NAME=raffles_db
DB_USER=raffles_user
DB_PASSWORD=una_contraseña_segura
DB_HOST=localhost
DB_PORT=5432
```

**Importante:** Genera una `SECRET_KEY` segura para tu entorno de producción.

### 4.2. Aplicar Migraciones y Recolectar Estáticos

Ejecuta las migraciones de Django para configurar el esquema de la base de datos y recolecta los archivos estáticos.

```bash
source /var/www/raffles/venv/bin/activate
python manage.py migrate
python manage.py collectstatic
```

Asegúrate de que el usuario que corre Apache (`www-data`) tenga permisos sobre los directorios `media` y `staticfiles`.

```bash
sudo chown -R www-data:www-data /var/www/raffles/media /var/www/raffles/staticfiles
sudo chmod -R 755 /var/www/raffles/media /var/www/raffles/staticfiles
```

## 5. Configuración de Gunicorn

### 5.1. Crear un Servicio `systemd` para Gunicorn

Para que Gunicorn se ejecute como un servicio en segundo plano, crea un archivo de servicio de `systemd`.

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Pega la siguiente configuración, ajustando las rutas y nombres de usuario si es necesario:

```ini
[Unit]
Description=gunicorn daemon for raffles app
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/raffles
ExecStart=/var/www/raffles/venv/bin/gunicorn --workers 3 --bind unix:/var/www/raffles/raffles.sock config.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 5.2. Iniciar y Habilitar el Servicio Gunicorn

Inicia el servicio y configúralo para que se inicie automáticamente con el sistema.

```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

Verifica que el socket se haya creado correctamente:

```bash
ls -l /var/www/raffles/raffles.sock
```

## 6. Configuración de Apache2 como Proxy Inverso

### 6.1. Crear Archivo de Configuración de Virtual Host

Crea un archivo de configuración para tu sitio en Apache.

```bash
sudo nano /etc/apache2/sites-available/raffles.conf
```

Añade la siguiente configuración. Reemplaza `tudominio.com` con tu nombre de dominio o la IP del servidor.

```apache
<VirtualHost *:80>
    ServerName tudominio.com
    ServerAdmin webmaster@localhost

    ProxyPreserveHost On
    ProxyPass / http://unix:/var/www/raffles/raffles.sock|http://127.0.0.1/
    ProxyPassReverse / http://unix:/var/www/raffles/raffles.sock|http://127.0.0.1/

    Alias /static/ /var/www/raffles/staticfiles/
    <Directory /var/www/raffles/staticfiles>
        Require all granted
    </Directory>

    Alias /media/ /var/www/raffles/media/
    <Directory /var/www/raffles/media>
        Require all granted
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
```

### 6.2. Habilitar Módulos y Sitio

Habilita los módulos de proxy de Apache, el nuevo sitio y reinicia el servicio.

```bash
sudo a2enmod proxy proxy_http
sudo a2ensite raffles.conf
sudo a2dissite 000-default.conf  # Opcional: deshabilita el sitio por defecto
sudo systemctl restart apache2
```

## 7. Verificación Final

Accede a `http://tudominio.com` en tu navegador. Deberías ver la aplicación de rifas funcionando.

Revisa los logs si encuentras algún error:
- **Logs de Gunicorn:** `sudo journalctl -u gunicorn`
- **Logs de Apache:** `sudo tail -f /var/log/apache2/error.log`