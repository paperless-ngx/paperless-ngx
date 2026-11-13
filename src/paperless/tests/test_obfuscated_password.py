import pytest

from paperless.fields import OBFUSCATED_PASSWORD_MASK
from paperless.fields import ObfuscatedPasswordField
from paperless.fields import is_obfuscated_password


class TestObfuscatedPasswordField:
    @pytest.mark.parametrize(
        "secret",
        [
            "a",
            "short",
            "exactly10!",
            "a-much-longer-secret-that-should-not-leak-its-length",
        ],
    )
    def test_representation_is_constant_regardless_of_length(self, secret: str) -> None:
        assert (
            ObfuscatedPasswordField().to_representation(secret)
            == OBFUSCATED_PASSWORD_MASK
        )


class TestIsObfuscatedPassword:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("", True),
            ("*", True),
            ("******", True),
            (OBFUSCATED_PASSWORD_MASK, True),
            ("real-secret", False),
            ("***x***", False),
            (" ", False),
        ],
    )
    def test_detects_placeholder(self, value: str, *, expected: bool) -> None:
        assert is_obfuscated_password(value) is expected
