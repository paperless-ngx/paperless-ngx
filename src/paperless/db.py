import gnupg

from django.conf import settings


class GnuPG(object):
    """
    A handy singleton to use when handling encrypted files.
    """

    gpg = gnupg.GPG(gnupghome=settings.GNUPG_HOME)

    @classmethod
    def decrypted(cls, file_handle):
        return cls.gpg.decrypt_file(
            file_handle, passphrase=settings.PASSPHRASE).data

    @classmethod
    def encrypted(cls, file_handle):
        return cls.gpg.encrypt_file(
            file_handle,
            recipients=None,
            passphrase=settings.PASSPHRASE,
            symmetric=True
        ).data
