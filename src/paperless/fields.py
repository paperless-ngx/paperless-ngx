from rest_framework import serializers

OBFUSCATED_PASSWORD_MASK = "*" * 10


def is_obfuscated_password(value: str) -> bool:
    """
    True if the value is only mask characters (or empty), meaning a client echoed
    the placeholder back rather than supplying a new secret
    """
    return value.replace("*", "") == ""


class ObfuscatedPasswordField(serializers.CharField):
    """
    Sends a constant mask string instead of the password in the clear
    """

    def to_representation(self, value) -> str:
        return OBFUSCATED_PASSWORD_MASK

    def to_internal_value(self, data):
        return data
