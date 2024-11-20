from unittest import mock

from allauth.mfa.models import Authenticator
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialApp
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from documents.tests.utils import DirectoriesMixin


# see allauth.socialaccount.providers.openid.provider.OpenIDProvider
class MockOpenIDProvider:
    id = "openid"
    name = "OpenID"

    def get_brands(self):
        default_servers = [
            dict(id="yahoo", name="Yahoo", openid_url="http://me.yahoo.com"),
            dict(id="hyves", name="Hyves", openid_url="http://hyves.nl"),
        ]
        return default_servers

    def get_login_url(self, request, **kwargs):
        return "openid/login/"


# see allauth.socialaccount.providers.openid_connect.provider.OpenIDConnectProviderAccount
class MockOpenIDConnectProviderAccount:
    def __init__(self, mock_social_account_dict):
        self.account = mock_social_account_dict

    def to_str(self):
        return self.account["name"]


# see allauth.socialaccount.providers.openid_connect.provider.OpenIDConnectProvider
class MockOpenIDConnectProvider:
    id = "openid_connect"
    name = "OpenID Connect"

    def __init__(self, app=None):
        self.app = app
        self.name = app.name

    def get_login_url(self, request, **kwargs):
        return f"{self.app.provider_id}/login/?process=connect"


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

    def setupSocialAccount(self):
        SocialApp.objects.create(
            name="Keycloak",
            provider="openid_connect",
            provider_id="keycloak-test",
        )
        self.user.socialaccount_set.add(
            SocialAccount(uid="123456789", provider="keycloak-test"),
            bulk=False,
        )

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

    @mock.patch(
        "allauth.socialaccount.models.SocialAccount.get_provider_account",
    )
    @mock.patch(
        "allauth.socialaccount.adapter.DefaultSocialAccountAdapter.list_providers",
    )
    def test_get_profile_w_social(self, mock_list_providers, mock_get_provider_account):
        """
        GIVEN:
            - Configured user and setup social account
        WHEN:
            - API call is made to get profile
        THEN:
            - Profile is returned with social accounts
        """
        self.setupSocialAccount()

        openid_provider = (
            MockOpenIDConnectProvider(
                app=SocialApp.objects.get(provider_id="keycloak-test"),
            ),
        )
        mock_list_providers.return_value = [
            openid_provider,
        ]
        mock_get_provider_account.return_value = MockOpenIDConnectProviderAccount(
            mock_social_account_dict={
                "name": openid_provider[0].name,
            },
        )

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            response.data["social_accounts"],
            [
                {
                    "id": 1,
                    "provider": "keycloak-test",
                    "name": "Keycloak",
                },
            ],
        )

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

    @mock.patch(
        "allauth.socialaccount.adapter.DefaultSocialAccountAdapter.list_providers",
    )
    def test_get_social_account_providers(
        self,
        mock_list_providers,
    ):
        """
        GIVEN:
            - Configured user
        WHEN:
            - API call is made to get social account providers
        THEN:
            - Social account providers are returned
        """
        self.setupSocialAccount()

        mock_list_providers.return_value = [
            MockOpenIDConnectProvider(
                app=SocialApp.objects.get(provider_id="keycloak-test"),
            ),
        ]

        response = self.client.get(f"{self.ENDPOINT}social_account_providers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data[0]["name"],
            "Keycloak",
        )
        self.assertIn(
            "keycloak-test/login/?process=connect",
            response.data[0]["login_url"],
        )

    @mock.patch(
        "allauth.socialaccount.adapter.DefaultSocialAccountAdapter.list_providers",
    )
    def test_get_social_account_providers_openid(
        self,
        mock_list_providers,
    ):
        """
        GIVEN:
            - Configured user and openid social account provider
        WHEN:
            - API call is made to get social account providers
        THEN:
            - Brands for openid provider are returned
        """

        mock_list_providers.return_value = [
            MockOpenIDProvider(),
        ]

        response = self.client.get(f"{self.ENDPOINT}social_account_providers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data),
            2,
        )

    def test_disconnect_social_account(self):
        """
        GIVEN:
            - Configured user
        WHEN:
            - API call is made to disconnect a social account
        THEN:
            - Social account is deleted from the user or request fails
        """
        self.setupSocialAccount()

        # Test with invalid id
        response = self.client.post(
            f"{self.ENDPOINT}disconnect_social_account/",
            {"id": -1},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test with valid id
        social_account_id = self.user.socialaccount_set.all()[0].pk

        response = self.client.post(
            f"{self.ENDPOINT}disconnect_social_account/",
            {"id": social_account_id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, social_account_id)

        self.assertEqual(
            len(self.user.socialaccount_set.filter(pk=social_account_id)),
            0,
        )


class TestApiTOTPViews(APITestCase):
    ENDPOINT = "/api/profile/totp/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_get_totp(self):
        """
        GIVEN:
            - Existing user account
        WHEN:
            - API request is made to TOTP endpoint
        THEN:
            - TOTP is generated
        """
        response = self.client.get(
            self.ENDPOINT,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("qr_svg", response.data)
        self.assertIn("secret", response.data)

    @mock.patch("allauth.mfa.totp.internal.auth.validate_totp_code")
    def test_activate_totp(self, mock_validate_totp_code):
        """
        GIVEN:
            - Existing user account
        WHEN:
            - API request is made to activate TOTP
        THEN:
            - TOTP is activated, recovery codes are returned
        """
        mock_validate_totp_code.return_value = True

        response = self.client.post(
            self.ENDPOINT,
            data={
                "secret": "123",
                "code": "456",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Authenticator.objects.filter(user=self.user).exists())
        self.assertIn("recovery_codes", response.data)

    def test_deactivate_totp(self):
        """
        GIVEN:
            - Existing user account with TOTP enabled
        WHEN:
            - API request is made to deactivate TOTP
        THEN:
            - TOTP is deactivated
        """
        Authenticator.objects.create(
            user=self.user,
            type=Authenticator.Type.TOTP,
            data={},
        )

        response = self.client.delete(
            self.ENDPOINT,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Authenticator.objects.filter(user=self.user).count(), 0)

        # test fails
        response = self.client.delete(
            self.ENDPOINT,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
