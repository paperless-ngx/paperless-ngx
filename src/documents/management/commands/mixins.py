import base64
import os
from argparse import ArgumentParser
from typing import Final
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.core.management import CommandError


class MultiProcessMixin:
    """
    Small class to handle adding an argument and validating it
    for the use of multiple processes
    """

    def add_argument_processes_mixin(self, parser: ArgumentParser):
        parser.add_argument(
            "--processes",
            default=max(1, os.cpu_count() // 4),
            type=int,
            help="Number of processes to distribute work amongst",
        )

    def handle_processes_mixin(self, *args, **options):
        self.process_count = options["processes"]
        if self.process_count < 1:
            raise CommandError("There must be at least 1 process")


class ProgressBarMixin:
    """
    Many commands use a progress bar, which can be disabled
    via this class
    """

    def add_argument_progress_bar_mixin(self, parser: ArgumentParser):
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown",
        )

    def handle_progress_bar_mixin(self, *args, **options):
        self.no_progress_bar = options["no_progress_bar"]
        self.use_progress_bar = not self.no_progress_bar


class SecurityMixin:
    """
    https://cryptography.io/en/latest/fernet/#using-passwords-with-fernet
    """

    # This matches to Django's default for now
    # https://github.com/django/django/blob/adae61942/django/contrib/auth/hashers.py#L315
    KEY_ITERATIONS: Final[int] = 1_000_000

    def setup_crypto(self, salt: Optional[str]):
        self.salt = salt or os.urandom(16).hex()
        self.fernet = self.get_fernet(self.passphrase, self.salt)

    def get_fernet(self, passphrase: str, salt: str) -> Fernet:
        """
        Constructs a class for encryption or decryption using the specified passphrase and salt

        Salt is assumed to be a hexadecimal representation of a cryptographically secure random byte string
        """

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=bytes.fromhex(salt),
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return Fernet(key)

    def encrypt_field(self, value: str) -> str:
        """
        Given a string field value, encrypts it and returns the hexadecimal representation of the encrypted token
        """
        return self.fernet.encrypt(value.encode("utf-8")).hex()

    def decrypt_field(self, value: str) -> str:
        """
        Given a string field value, decrypts it and returns the original value of the field
        """
        return self.fernet.decrypt(bytes.fromhex(value)).decode("utf-8")
