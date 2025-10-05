from .models import SiteSettings

def site_settings(request):
    try:
        settings = SiteSettings.objects.latest('id')
    except SiteSettings.DoesNotExist:
        settings = None
    return {'site_settings': settings}