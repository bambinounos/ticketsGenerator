import os
from django.apps import AppConfig
from django.conf import settings


class RafflesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "raffles"

    def ready(self):
        # Ensure media directory exists to prevent 500 errors on file upload
        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            try:
                os.makedirs(media_root, exist_ok=True)
                # Also create favicons subdirectory
                os.makedirs(os.path.join(media_root, 'favicons'), exist_ok=True)
            except OSError:
                # If we cannot create it (permissions), we log it but don't crash startup
                pass
