from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from paperless.auth import AutoLoginMiddleware
from paperless_testing.factories import UserFactory


@override_settings(AUTO_LOGIN_USERNAME="autologin")
class TestAutoLoginMiddleware(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = AutoLoginMiddleware(lambda request: None)

    def _process(self, request):
        # login() needs a session to write to
        request.session = self.client.session
        self.middleware.process_request(request)
        return request

    def test_active_user_is_logged_in(self) -> None:
        """
        GIVEN:
            - AUTO_LOGIN_USERNAME names an active user
        WHEN:
            - A request is processed by the middleware
        THEN:
            - That user is attached to the request
        """
        user = UserFactory(username="autologin")

        request = self._process(self.factory.get("/"))

        self.assertEqual(request.user, user)

    def test_deactivated_user_is_not_logged_in(self) -> None:
        """
        GIVEN:
            - AUTO_LOGIN_USERNAME names a user who has been deactivated
        WHEN:
            - A request is processed by the middleware
        THEN:
            - The request is left anonymous rather than authenticated as them
        """
        UserFactory(username="autologin", is_active=False)

        request = self.factory.get("/")
        request.user = AnonymousUser()
        self._process(request)

        self.assertFalse(request.user.is_authenticated)

    @override_settings(FORCE_SCRIPT_NAME="/paperless")
    def test_token_request_is_not_logged_in_under_subpath(self) -> None:
        """
        GIVEN:
            - Paperless is served under a subpath
        WHEN:
            - A token is requested via POST
        THEN:
            - The request is left anonymous so the posted credentials are used
        """
        UserFactory(username="autologin")

        request = self.factory.post("/api/token/")
        request.user = AnonymousUser()
        self._process(request)

        self.assertFalse(request.user.is_authenticated)
