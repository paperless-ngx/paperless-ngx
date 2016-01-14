import gnupg

from django.conf import settings


class GnuPG(object):
    """
    A handy singleton to use when handling encrypted files.
    """

    gpg = gnupg.GPG(gnupghome=settings.GNUPG_HOME)

    @classmethod
    def decrypted(cls, path):
        return cls.gpg.decrypt_file(path, passphrase=settings.PASSPHRASE).data

    @classmethod
    def encrypted(cls, path):
        return cls.gpg.encrypt_file(
            path,
            recipients=None,
            passphrase=settings.PASSPHRASE,
            symmetric=True
        ).data
