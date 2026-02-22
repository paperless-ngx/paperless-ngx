import json
from urllib.parse import parse_qs
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token

from paperless.external_auth import EXTERNAL_AUTH_FLOW_SESSION_KEY


@override_settings(
    EXTERNAL_AUTH_ALLOWED_REDIRECT_URIS=["app://callback"],
    EXTERNAL_AUTH_CODE_TTL_SECONDS=60,
    EXTERNAL_AUTH_FLOW_TTL_SECONDS=600,
)
class TestExternalAuth(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user("external-auth-user")
        self.code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        self.code_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

    def _set_external_flow(self, redirect_uri: str = "app://callback", state="abc"):
        session = self.client.session
        session[EXTERNAL_AUTH_FLOW_SESSION_KEY] = {
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "created_at": 9999999999,
        }
        session.save()

    def _start_payload(
        self,
        *,
        redirect_uri: str = "app://callback",
        state: str | None = "mobile-state",
    ) -> dict[str, str]:
        payload = {
            "redirect_uri": redirect_uri,
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
        }
        if state is not None:
            payload["state"] = state
        return payload

    @override_settings(EXTERNAL_AUTH_ALLOWED_REDIRECT_URIS=[])
    def test_start_requires_external_auth_configuration(self) -> None:
        response = self.client.get(
            "/api/auth/external-login/start/",
            self._start_payload(),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertContains(
            response,
            "External app login unavailable",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    def test_start_rejects_invalid_redirect_uri(self) -> None:
        response = self.client.get(
            "/api/auth/external-login/start/",
            self._start_payload(redirect_uri="app://other-callback"),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        EXTERNAL_AUTH_ALLOWED_REDIRECT_URIS=["https://example.com/callback"],
    )
    def test_start_allows_allowlisted_https_redirect_uri(self) -> None:
        response = self.client.get(
            "/api/auth/external-login/start/",
            self._start_payload(redirect_uri="https://example.com/callback"),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            response["Location"],
            "/accounts/login/?next=%2Fapi%2Fauth%2Fexternal-login%2Fcomplete%2F",
        )

    def test_start_requires_pkce_parameters(self) -> None:
        response = self.client.get(
            "/api/auth/external-login/start/",
            {"redirect_uri": "app://callback"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertContains(
            response,
            "Missing PKCE code challenge.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    def test_start_rejects_invalid_pkce_method(self) -> None:
        response = self.client.get(
            "/api/auth/external-login/start/",
            {
                "redirect_uri": "app://callback",
                "code_challenge": self.code_challenge,
                "code_challenge_method": "plain",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertContains(
            response,
            "Unsupported PKCE code challenge method.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    def test_start_stores_flow_and_redirects_to_login(self) -> None:
        response = self.client.get(
            "/api/auth/external-login/start/",
            self._start_payload(),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            response["Location"],
            "/accounts/login/?next=%2Fapi%2Fauth%2Fexternal-login%2Fcomplete%2F",
        )

        session = self.client.session
        self.assertEqual(
            session[EXTERNAL_AUTH_FLOW_SESSION_KEY]["redirect_uri"],
            "app://callback",
        )
        self.assertEqual(
            session[EXTERNAL_AUTH_FLOW_SESSION_KEY]["state"],
            "mobile-state",
        )
        self.assertEqual(
            session[EXTERNAL_AUTH_FLOW_SESSION_KEY]["code_challenge"],
            self.code_challenge,
        )
        self.assertEqual(
            session[EXTERNAL_AUTH_FLOW_SESSION_KEY]["code_challenge_method"],
            "S256",
        )

    def test_start_for_authenticated_user_redirects_to_complete(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/auth/external-login/start/",
            self._start_payload(),
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response["Location"], "/api/auth/external-login/complete/")

    def test_complete_without_flow_returns_bad_request(self) -> None:
        response = self.client.get("/api/auth/external-login/complete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertContains(
            response,
            "Login request expired",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    def test_complete_for_unauthenticated_user_redirects_to_login(self) -> None:
        self._set_external_flow()

        response = self.client.get("/api/auth/external-login/complete/")
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            response["Location"],
            "/accounts/login/?next=%2Fapi%2Fauth%2Fexternal-login%2Fcomplete%2F",
        )

    def test_complete_and_exchange_flow(self) -> None:
        self.client.force_login(self.user)
        self._set_external_flow(state="state-123")

        complete_response = self.client.get("/api/auth/external-login/complete/")
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertContains(complete_response, "Approve app access")
        self.assertContains(complete_response, "Approve and continue")
        self.assertContains(complete_response, "Deny")
        self.assertEqual(complete_response.context["callback_uri"], "app://callback")

        approve_response = self.client.post(
            "/api/auth/external-login/complete/",
            {"action": "approve"},
        )
        self.assertEqual(approve_response.status_code, status.HTTP_302_FOUND)

        parsed = urlparse(approve_response["Location"])
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "app")
        self.assertEqual(parsed.netloc, "callback")
        self.assertEqual(query["state"][0], "state-123")
        self.assertIn("code", query)
        code = query["code"][0]

        exchange_response = self.client.post(
            "/api/auth/external-login/exchange/",
            data=json.dumps(
                {
                    "code": code,
                    "code_verifier": self.code_verifier,
                    "redirect_uri": "app://callback",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(exchange_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            exchange_response.json()["token"],
            Token.objects.get(user=self.user).key,
        )

        replay_response = self.client.post(
            "/api/auth/external-login/exchange/",
            data=json.dumps(
                {
                    "code": code,
                    "code_verifier": self.code_verifier,
                    "redirect_uri": "app://callback",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(replay_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_deny_redirects_with_error(self) -> None:
        self.client.force_login(self.user)
        self._set_external_flow(state="state-123")

        deny_response = self.client.post(
            "/api/auth/external-login/complete/",
            {"action": "deny"},
        )
        self.assertEqual(deny_response.status_code, status.HTTP_302_FOUND)

        parsed = urlparse(deny_response["Location"])
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "app")
        self.assertEqual(query["error"][0], "access_denied")
        self.assertEqual(query["state"][0], "state-123")

    def test_exchange_rejects_redirect_uri_mismatch(self) -> None:
        self.client.force_login(self.user)
        self._set_external_flow(state="state-123")
        approve_response = self.client.post(
            "/api/auth/external-login/complete/",
            {"action": "approve"},
        )
        code = parse_qs(urlparse(approve_response["Location"]).query)["code"][0]

        response = self.client.post(
            "/api/auth/external-login/exchange/",
            data=json.dumps(
                {
                    "code": code,
                    "code_verifier": self.code_verifier,
                    "redirect_uri": "app://other-callback",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exchange_rejects_invalid_code_verifier(self) -> None:
        self.client.force_login(self.user)
        self._set_external_flow(state="state-123")
        approve_response = self.client.post(
            "/api/auth/external-login/complete/",
            {"action": "approve"},
        )
        code = parse_qs(urlparse(approve_response["Location"]).query)["code"][0]

        response = self.client.post(
            "/api/auth/external-login/exchange/",
            data=json.dumps(
                {
                    "code": code,
                    "code_verifier": "not-valid",
                    "redirect_uri": "app://callback",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exchange_rejects_unknown_code(self) -> None:
        response = self.client.post(
            "/api/auth/external-login/exchange/",
            data=json.dumps(
                {
                    "code": "unknown",
                    "code_verifier": self.code_verifier,
                    "redirect_uri": "app://callback",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
