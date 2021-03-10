from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase


class TestViews(TestCase):

    def setUp(self) -> None:
        self.user = User.objects.create_user("testuser")

    def test_login_redirect(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/login/?next=/")

    def test_index(self):
        self.client.force_login(self.user)
        for (language_given, language_actual) in [("", "en-US"), ("en-US", "en-US"), ("de", "de-DE"), ("en", "en-US"), ("en-us", "en-US"), ("fr", "fr-FR"), ("jp", "en-US")]:
            if language_given:
                self.client.cookies.load({settings.LANGUAGE_COOKIE_NAME: language_given})
            elif settings.LANGUAGE_COOKIE_NAME in self.client.cookies.keys():
                self.client.cookies.pop(settings.LANGUAGE_COOKIE_NAME)

            response = self.client.get('/', )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context_data['webmanifest'], f"frontend/{language_actual}/manifest.webmanifest")
            self.assertEqual(response.context_data['styles_css'], f"frontend/{language_actual}/styles.css")
            self.assertEqual(response.context_data['runtime_js'], f"frontend/{language_actual}/runtime.js")
            self.assertEqual(response.context_data['polyfills_js'], f"frontend/{language_actual}/polyfills.js")
            self.assertEqual(response.context_data['main_js'], f"frontend/{language_actual}/main.js")
