from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from documents.tests.utils import DirectoriesMixin


class TestApiProfile(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/profile/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(
            username="temp_admin",
            first_name="firstname",
            last_name="surname",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_profile(self):
        """
        GIVEN:
            - Configured user
        WHEN:
            - API call is made to get profile
        THEN:
            - Profile is returned
        """

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["first_name"], self.user.first_name)
        self.assertEqual(response.data["last_name"], self.user.last_name)

    def test_update_profile(self):
        """
        GIVEN:
            - Configured user
        WHEN:
            - API call is made to update profile
        THEN:
            - Profile is updated
        """

        user_data = {
            "email": "new@email.com",
            "password": "superpassword1234",
            "first_name": "new first name",
            "last_name": "new last name",
        }
        response = self.client.patch(self.ENDPOINT, user_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(username=self.user.username)
        self.assertTrue(user.check_password(user_data["password"]))
        self.assertEqual(user.email, user_data["email"])
        self.assertEqual(user.first_name, user_data["first_name"])
        self.assertEqual(user.last_name, user_data["last_name"])

    def test_update_auth_token(self):
        """
        GIVEN:
            - Configured user
        WHEN:
            - API call is made to generate auth token
        THEN:
            - Token is created the first time, updated the second
        """

        self.assertEqual(len(Token.objects.all()), 0)

        response = self.client.post(f"{self.ENDPOINT}generate_auth_token/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token1 = Token.objects.filter(user=self.user).first()
        self.assertIsNotNone(token1)

        response = self.client.post(f"{self.ENDPOINT}generate_auth_token/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token2 = Token.objects.filter(user=self.user).first()

        self.assertNotEqual(token1.key, token2.key)

    def test_profile_not_logged_in(self):
        """
        GIVEN:
            - User not logged in
        WHEN:
            - API call is made to get profile and update token
        THEN:
            - Profile is returned
        """

        self.client.logout()

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post(f"{self.ENDPOINT}generate_auth_token/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
