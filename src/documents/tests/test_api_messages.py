from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase

from documents.tests.utils import DirectoriesMixin
from paperless.views import MessagesView


class TestApiMessages(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/messages/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(
            username="temp_admin",
            first_name="firstname",
            last_name="surname",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_django_messages(self):
        """
        GIVEN:
            - Configured user
            - Pending django message
        WHEN:
            - API call is made to get the django messages
        THEN:
            - Pending message is returned
            - No more messages are pending
        """

        factory = RequestFactory()

        request = factory.get(self.ENDPOINT)
        request.user = self.user

        # Fake middleware support for RequestFactory
        # See https://stackoverflow.com/a/66473588/1022690
        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

        msg = "Test message"
        messages.error(request, msg)

        response = MessagesView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["level"], "error")
        self.assertEqual(response.data[0]["message"], msg)
