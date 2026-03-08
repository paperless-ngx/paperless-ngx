import copy
import os
from collections.abc import Callable
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from typing import TypeVar
from typing import overload

T = TypeVar("T")


def str_to_bool(value: str) -> bool:
    """
    Converts a string representation of truth to a boolean value.

    Recognizes 'true', '1', 't', 'y', 'yes' as True, and
    'false', '0', 'f', 'n', 'no' as False. Case-insensitive.

    Args:
        value: The string to convert.

    Returns:
        The boolean representation of the string.

    Raises:
        ValueError: If the string is not a recognized boolean value.
    """
    val_lower = value.strip().lower()
    if val_lower in ("true", "1", "t", "y", "yes"):
        return True
    elif val_lower in ("false", "0", "f", "n", "no"):
        return False
    raise ValueError(f"Cannot convert '{value}' to a boolean.")


@overload
def get_int_from_env(key: str) -> int | None: ...


@overload
def get_int_from_env(key: str, default: None) -> int | None: ...


@overload
def get_int_from_env(key: str, default: int) -> int: ...


def get_int_from_env(key: str, default: int | None = None) -> int | None:
    """
    Return an integer value based on the environment variable.
    If default is provided, returns that value when key is missing.
    If default is None, returns None when key is missing.
    """
    if key not in os.environ:
        return default

    return int(os.environ[key])


def parse_dict_from_str(
    env_str: str | None,
    defaults: dict[str, Any] | None = None,
    type_map: Mapping[str, Callable[[str], Any]] | None = None,
    separator: str = ",",
) -> dict[str, Any]:
    """
    Parses a key-value string into a dictionary, applying defaults and casting types.

    Supports nested keys via dot-notation, e.g.:
        "database.host=localhost,database.port=5432"

    Args:
        env_str: The string from the environment variable (e.g., "port=9090,debug=true").
        defaults: A dictionary of default values (can contain nested dicts).
        type_map: A dictionary mapping keys (dot-notation allowed) to a type or a parsing
                  function (e.g., {'port': int, 'debug': bool, 'database.port': int}).
                  The special `bool` type triggers custom boolean parsing.
        separator: The character used to separate key-value pairs. Defaults to ','.

    Returns:
        A dictionary with the parsed and correctly-typed settings.

    Raises:
        ValueError: If a value cannot be cast to its specified type.
    """

    def _set_nested(d: dict, keys: list[str], value: Any) -> None:
        """Set a nested value, creating intermediate dicts as needed."""
        cur = d
        for k in keys[:-1]:
            if k not in cur or not isinstance(cur[k], dict):
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = value

    def _get_nested(d: dict, keys: list[str]) -> Any:
        """Get nested value or raise KeyError if not present."""
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                raise KeyError
            cur = cur[k]
        return cur

    def _has_nested(d: dict, keys: list[str]) -> bool:
        try:
            _get_nested(d, keys)
            return True
        except KeyError:
            return False

    settings: dict[str, Any] = copy.deepcopy(defaults) if defaults else {}
    _type_map = type_map if type_map else {}

    if not env_str:
        return settings

    # Parse the environment string using the specified separator
    pairs = [p.strip() for p in env_str.split(separator) if p.strip()]
    for pair in pairs:
        if "=" not in pair:
            # ignore malformed pairs
            continue
        key, val = pair.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        parts = key.split(".")
        _set_nested(settings, parts, val)

    # Apply type casting to the updated settings (supports nested keys in type_map)
    for key, caster in _type_map.items():
        key_parts = key.split(".")
        if _has_nested(settings, key_parts):
            raw_val = _get_nested(settings, key_parts)
            # Only cast if it's a string (i.e. from env parsing). If defaults already provided
            # a different type we leave it as-is.
            if isinstance(raw_val, str):
                try:
                    if caster is bool:
                        parsed = str_to_bool(raw_val)
                    elif caster is Path:
                        parsed = Path(raw_val).resolve()
                    else:
                        parsed = caster(raw_val)
                except (ValueError, TypeError) as e:
                    caster_name = getattr(caster, "__name__", repr(caster))
                    raise ValueError(
                        f"Error casting key '{key}' with value '{raw_val}' "
                        f"to type '{caster_name}'",
                    ) from e
                _set_nested(settings, key_parts, parsed)

    return settings


def get_choice_from_env(
    env_key: str,
    choices: set[str],
    default: str | None = None,
) -> str:
    """
    Gets and validates an environment variable against a set of allowed choices.

    Args:
        env_key: The environment variable key to validate
        choices: Set of valid choices for the environment variable
        default: Optional default value if environment variable is not set

    Returns:
        The validated environment variable value

    Raises:
        ValueError: If the environment variable value is not in choices
                             or if no default is provided and env var is missing
    """
    value = os.environ.get(env_key, default)

    if value is None:
        raise ValueError(
            f"Environment variable '{env_key}' is required but not set.",
        )

    if value not in choices:
        raise ValueError(
            f"Environment variable '{env_key}' has invalid value '{value}'. "
            f"Valid choices are: {', '.join(sorted(choices))}",
        )

    return value
