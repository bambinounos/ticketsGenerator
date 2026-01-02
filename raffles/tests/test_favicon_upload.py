from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from raffles.models import SiteSettings

class SiteSettingsAdminTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.login(username='admin', password='password')

    def test_upload_favicon_success(self):
        """Test that a valid favicon can be uploaded via the admin."""
        # Ensure no settings exist
        SiteSettings.objects.all().delete()

        # Create a small valid image
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
        favicon = SimpleUploadedFile(name='test_favicon.png', content=image_content, content_type='image/png')

        response = self.client.post('/admin/raffles/sitesettings/add/', {
            'favicon': favicon,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(SiteSettings.objects.exists())
        self.assertTrue(SiteSettings.objects.first().favicon)

    def test_singleton_permission(self):
        """Test that adding a second SiteSettings is not allowed."""
        # Create one setting
        SiteSettings.objects.create()

        # Try to access add page
        response = self.client.get('/admin/raffles/sitesettings/add/')
        # Should be 403 Forbidden because has_add_permission returns False
        self.assertEqual(response.status_code, 403)
