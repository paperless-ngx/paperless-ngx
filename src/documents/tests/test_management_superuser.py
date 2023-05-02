import os
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from documents.tests.utils import DirectoriesMixin


class TestManageSuperUser(DirectoriesMixin, TestCase):
    def call_command(self, environ):
        out = StringIO()
        with mock.patch.dict(os.environ, environ):
            call_command(
                "manage_superuser",
                "--no-color",
                stdout=out,
                stderr=StringIO(),
            )
        return out.getvalue()

    def test_no_user(self):
        """
        GIVEN:
            - Environment does not contain admin user info
        THEN:
            - No admin user is created
        """

        out = self.call_command(environ={})

        # just the consumer user which is created
        # during migration, and AnonymousUser
        self.assertEqual(User.objects.count(), 2)
        self.assertTrue(User.objects.filter(username="consumer").exists())
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 0)
        self.assertEqual(
            out,
            "Please check if PAPERLESS_ADMIN_PASSWORD has been set in the environment\n",
        )

    def test_create(self):
        """
        GIVEN:
            - Environment does contain admin user password
        THEN:
            - admin user is created
        """

        out = self.call_command(environ={"PAPERLESS_ADMIN_PASSWORD": "123456"})

        # count is 3 as there's the consumer
        # user already created during migration, and AnonymousUser
        user: User = User.objects.get_by_natural_key("admin")
        self.assertEqual(User.objects.count(), 3)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "root@localhost")
        self.assertEqual(out, 'Created superuser "admin" with provided password.\n')

    def test_some_superuser_exists(self):
        """
        GIVEN:
            - A super user already exists
            - Environment does contain admin user password
        THEN:
            - admin user is NOT created
        """
        User.objects.create_superuser("someuser", "root@localhost", "password")

        out = self.call_command(environ={"PAPERLESS_ADMIN_PASSWORD": "123456"})

        self.assertEqual(User.objects.count(), 3)
        with self.assertRaises(User.DoesNotExist):
            User.objects.get_by_natural_key("admin")
        self.assertEqual(
            out,
            "Did not create superuser, the DB already contains superusers\n",
        )

    def test_admin_superuser_exists(self):
        """
        GIVEN:
            - A super user already exists
            - The existing superuser's username is admin
            - Environment does contain admin user password
        THEN:
            - Password remains unchanged
        """
        User.objects.create_superuser("admin", "root@localhost", "password")

        out = self.call_command(environ={"PAPERLESS_ADMIN_PASSWORD": "123456"})

        self.assertEqual(User.objects.count(), 3)
        user: User = User.objects.get_by_natural_key("admin")
        self.assertTrue(user.check_password("password"))
        self.assertEqual(out, "Did not create superuser, a user admin already exists\n")

    def test_admin_user_exists(self):
        """
        GIVEN:
            - A user already exists with the username admin
            - Environment does contain admin user password
        THEN:
            - Password remains unchanged
            - User is not upgraded to superuser
        """

        User.objects.create_user("admin", "root@localhost", "password")

        out = self.call_command(environ={"PAPERLESS_ADMIN_PASSWORD": "123456"})

        self.assertEqual(User.objects.count(), 3)
        user: User = User.objects.get_by_natural_key("admin")
        self.assertTrue(user.check_password("password"))
        self.assertFalse(user.is_superuser)
        self.assertEqual(out, "Did not create superuser, a user admin already exists\n")

    def test_no_password(self):
        """
        GIVEN:
            - No environment data is set
        THEN:
            - No user is created
        """
        out = self.call_command(environ={})

        with self.assertRaises(User.DoesNotExist):
            User.objects.get_by_natural_key("admin")
        self.assertEqual(
            out,
            "Please check if PAPERLESS_ADMIN_PASSWORD has been set in the environment\n",
        )

    def test_user_email(self):
        """
        GIVEN:
            - Environment does contain admin user password
            - Environment contains user email
        THEN:
            - admin user is created
        """

        out = self.call_command(
            environ={
                "PAPERLESS_ADMIN_PASSWORD": "123456",
                "PAPERLESS_ADMIN_MAIL": "hello@world.com",
            },
        )

        user: User = User.objects.get_by_natural_key("admin")
        self.assertEqual(User.objects.count(), 3)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "hello@world.com")
        self.assertEqual(user.username, "admin")
        self.assertEqual(out, 'Created superuser "admin" with provided password.\n')

    def test_user_username(self):
        """
        GIVEN:
            - Environment does contain admin user password
            - Environment contains user username
        THEN:
            - admin user is created
        """

        out = self.call_command(
            environ={
                "PAPERLESS_ADMIN_PASSWORD": "123456",
                "PAPERLESS_ADMIN_MAIL": "hello@world.com",
                "PAPERLESS_ADMIN_USER": "super",
            },
        )

        user: User = User.objects.get_by_natural_key("super")
        self.assertEqual(User.objects.count(), 3)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "hello@world.com")
        self.assertEqual(user.username, "super")
        self.assertEqual(out, 'Created superuser "super" with provided password.\n')
