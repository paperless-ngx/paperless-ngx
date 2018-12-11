from django.contrib.auth.models import User as DjangoUser


class User:
    """
    This is a dummy django User used with our middleware to disable
    login authentication if that is configured in paperless.conf
    """

    is_superuser = True
    is_active = True
    is_staff = True
    is_authenticated = True

    @property
    def id(self):
        return DjangoUser.objects.order_by("pk").first().pk

    @property
    def pk(self):
        return self.id


"""
NOTE: These are here as a hack instead of being in the User definition
NOTE: above due to the way pycodestyle handles lamdbdas.
NOTE: See https://github.com/PyCQA/pycodestyle/issues/379 for more.
"""

User.has_module_perms = lambda *_: True
User.has_perm = lambda *_: True
