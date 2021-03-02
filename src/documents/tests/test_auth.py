from django.contrib.auth.models import User
from django.test import override_settings, Client, modify_settings, TestCase


class TestRemoteUserAuthentication(TestCase):

    def test_no_remote_user_auth(self):
        client = Client()

        response = client.get("/api/documents/")
        self.assertEqual(response.status_code, 401)

        response = client.get("/api/documents/", HTTP_REMOTE_USER="someone")
        self.assertEqual(response.status_code, 401)

        response = client.get("/api/documents/", HTTP_X_FORWARDED_USER="someone")
        self.assertEqual(response.status_code, 401)

    @modify_settings(
        MIDDLEWARE={
            'append': 'paperless.auth.HttpRemoteUserMiddleware'
        },
        AUTHENTICATION_BACKENDS={
            'prepend': 'django.contrib.auth.backends.RemoteUserBackend'
        }
    )
    def test_standard_remote_user_auth(self):
        client = Client()

        response = client.get("/api/documents/")
        self.assertEqual(response.status_code, 401)

        response = client.get("/api/documents/", HTTP_X_FORWARDED_USER="someone")
        self.assertEqual(response.status_code, 401)

        self.assertFalse(User.objects.filter(username="someone").exists())

        response = client.get("/api/documents/", HTTP_REMOTE_USER="someone")
        self.assertEqual(response.status_code, 200)

        self.assertTrue(User.objects.filter(username="someone").exists())

    @modify_settings(
        MIDDLEWARE={
            'append': 'paperless.auth.HttpRemoteUserMiddleware'
        },
        AUTHENTICATION_BACKENDS={
            'prepend': 'django.contrib.auth.backends.RemoteUserBackend'
        }
    )
    @override_settings(HTTP_REMOTE_USER_HEADER_NAME="HTTP_X_FORWARDED_USER")
    def test_custom_remote_user_auth(self):
        client = Client()

        response = client.get("/api/documents/")
        self.assertEqual(response.status_code, 401)

        response = client.get("/api/documents/", HTTP_REMOTE_USER="someone")
        self.assertEqual(response.status_code, 401)

        self.assertFalse(User.objects.filter(username="someone").exists())

        response = client.get("/api/documents/", HTTP_X_FORWARDED_USER="someone")
        self.assertEqual(response.status_code, 200)

        self.assertTrue(User.objects.filter(username="someone").exists())
