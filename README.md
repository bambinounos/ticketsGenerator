# Software de Generación de Rifas

Este es un software de código abierto para la generación y gestión de rifas, desarrollado con Python y Django. Permite a los usuarios crear rifas, gestionar clientes, y generar boletos personalizados de forma eficiente.

## Características

- **Gestión de Rifas:** Crea y administra múltiples rifas, cada una con su propio nombre, año y descripción.
- **Personalización de Boletos:** Diseña plantillas de boletos personalizadas con colores de fondo, colores de fuente e imágenes de fondo.
- **Gestión de Clientes:** Almacena y gestiona la información de los clientes que compran boletos.
- **Generación de Boletos:** Genera boletos únicos para cada cliente con números de boleto y códigos QR para verificación.
- **Configuración del Sitio:** Personaliza el favicon del sitio a través del panel de administración de Django.

## Tecnologías Utilizadas

- **Backend:** Python, Django
- **Base de Datos:** PostgreSQL
- **Servidor de Aplicaciones:** Gunicorn
- **Variables de Entorno:** python-decouple
- **Manejo de Imágenes:** Pillow

## Prerrequisitos

- Python 3.8 o superior
- PostgreSQL
- Git

## Instalación y Configuración

1. **Clona el repositorio:**
   ```bash
   git clone <URL-del-repositorio>
   cd <nombre-del-repositorio>
   ```

2. **Crea y activa un entorno virtual:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura las variables de entorno:**
   Crea un archivo `.env` en la raíz del proyecto y añade las siguientes variables:
   ```env
   SECRET_KEY=tu_super_secreto_aqui
   DEBUG=True
   DB_NAME=raffles_db
   DB_USER=raffles_user
   DB_PASSWORD=password
   DB_HOST=localhost
   DB_PORT=5432
   ```

5. **Configura la base de datos:**
   Asegúrate de que PostgreSQL esté en funcionamiento y de que la base de datos y el usuario especificados en el archivo `.env` existan.

6. **Aplica las migraciones:**
   ```bash
   python manage.py migrate
   ```

7. **Crea un superusuario:**
   ```bash
   python manage.py createsuperuser
   ```

## Cómo Correr la Aplicación

Para iniciar el servidor de desarrollo, ejecuta:
```bash
python manage.py runserver
```
La aplicación estará disponible en `http://127.0.0.1:8000`.

## Cómo Correr las Pruebas

Para ejecutar las pruebas, utiliza el siguiente comando:
```bash
python manage.py test
```

## Despliegue

Para un entorno de producción, se recomienda utilizar Gunicorn como servidor de aplicaciones y un servidor proxy como Nginx o Apache. Asegúrate de que `DEBUG` esté configurado como `False` en tu archivo `.env` para producción.

## Estructura del Proyecto

```
.
├── config/             # Configuración del proyecto Django
├── raffles/            # Aplicación principal de Django
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   └── views.py
├── .gitignore
├── manage.py
└── requirements.txt
```