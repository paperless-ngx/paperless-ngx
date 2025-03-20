import base64
import os
from argparse import ArgumentParser
from typing import TypedDict

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.core.management import CommandError

from documents.settings import EXPORTER_CRYPTO_ALGO_NAME
from documents.settings import EXPORTER_CRYPTO_KEY_ITERATIONS_NAME
from documents.settings import EXPORTER_CRYPTO_KEY_SIZE_NAME
from documents.settings import EXPORTER_CRYPTO_SALT_NAME
from documents.settings import EXPORTER_CRYPTO_SETTINGS_NAME


class CryptFields(TypedDict):
    exporter_key: str
    model_name: str
    fields: list[str]


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


class CryptMixin:
    """
    Fully based on:
    https://cryptography.io/en/latest/fernet/#using-passwords-with-fernet

    To encrypt:
      1. Call setup_crypto providing the user provided passphrase
      2. Call encrypt_string with a value
      3. Store the returned hexadecimal representation of the value

    To decrypt:
      1. Load the required parameters:
        a. key iterations
        b. key size
        c. key algorithm
      2. Call setup_crypto providing the user provided passphrase and stored salt
      3. Call decrypt_string with a value
      4. Use the returned value

    """

    # This matches to Django's default for now
    # https://github.com/django/django/blob/adae61942/django/contrib/auth/hashers.py#L315

    # Set the defaults to be used during export
    # During import, these are overridden from the loaded values to ensure decryption is possible
    key_iterations = 1_000_000
    salt_size = 16
    key_size = 32
    kdf_algorithm = "pbkdf2_sha256"

    CRYPT_FIELDS: CryptFields = [
        {
            "exporter_key": "mail_accounts",
            "model_name": "paperless_mail.mailaccount",
            "fields": [
                "password",
                "refresh_token",
            ],
        },
        {
            "exporter_key": "social_tokens",
            "model_name": "socialaccount.socialtoken",
            "fields": [
                "token",
                "token_secret",
            ],
        },
    ]

    def get_crypt_params(self) -> dict[str, dict[str, str | int]]:
        return {
            EXPORTER_CRYPTO_SETTINGS_NAME: {
                EXPORTER_CRYPTO_ALGO_NAME: self.kdf_algorithm,
                EXPORTER_CRYPTO_KEY_ITERATIONS_NAME: self.key_iterations,
                EXPORTER_CRYPTO_KEY_SIZE_NAME: self.key_size,
                EXPORTER_CRYPTO_SALT_NAME: self.salt,
            },
        }

    def load_crypt_params(self, metadata: dict):
        # Load up the values for setting up decryption
        self.kdf_algorithm: str = metadata[EXPORTER_CRYPTO_SETTINGS_NAME][
            EXPORTER_CRYPTO_ALGO_NAME
        ]
        self.key_iterations: int = metadata[EXPORTER_CRYPTO_SETTINGS_NAME][
            EXPORTER_CRYPTO_KEY_ITERATIONS_NAME
        ]
        self.key_size: int = metadata[EXPORTER_CRYPTO_SETTINGS_NAME][
            EXPORTER_CRYPTO_KEY_SIZE_NAME
        ]
        self.salt: str = metadata[EXPORTER_CRYPTO_SETTINGS_NAME][
            EXPORTER_CRYPTO_SALT_NAME
        ]

    def setup_crypto(self, *, passphrase: str, salt: str | None = None):
        """
        Constructs a class for encryption or decryption using the specified passphrase and salt

        Salt is assumed to be a hexadecimal representation of a cryptographically secure random byte string.
        If not provided, it will be derived from the system secure random
        """
        self.salt = salt or os.urandom(self.salt_size).hex()

        # Derive the KDF based on loaded settings
        if self.kdf_algorithm == "pbkdf2_sha256":
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=self.key_size,
                salt=bytes.fromhex(self.salt),
                iterations=self.key_iterations,
            )
        else:  # pragma: no cover
            raise CommandError(
                f"{self.kdf_algorithm} is an unknown key derivation function",
            )

        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))

        self.fernet = Fernet(key)

    def encrypt_string(self, *, value: str) -> str:
        """
        Given a string value, encrypts it and returns the hexadecimal representation of the encrypted token

        """
        return self.fernet.encrypt(value.encode("utf-8")).hex()

    def decrypt_string(self, *, value: str) -> str:
        """
        Given a string value, decrypts it and returns the original value of the field
        """
        return self.fernet.decrypt(bytes.fromhex(value)).decode("utf-8")
