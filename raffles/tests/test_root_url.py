from django.test import TestCase, Client
from django.urls import reverse

class RootURLTest(TestCase):
    def test_root_url_resolves(self):
        client = Client()
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'raffles/home.html')
