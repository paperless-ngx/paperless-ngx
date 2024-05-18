import gnupg
from django.conf import settings


class GnuPG:
    """
    A handy singleton to use when handling encrypted files.
    """

    gpg = gnupg.GPG(gnupghome=settings.GNUPG_HOME)

    @classmethod
    def decrypted(cls, file_handle, passphrase=None):
        if not passphrase:
            passphrase = settings.PASSPHRASE

        return cls.gpg.decrypt_file(file_handle, passphrase=passphrase).data
