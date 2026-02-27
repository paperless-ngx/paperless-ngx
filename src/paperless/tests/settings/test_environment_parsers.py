import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from paperless.settings.parsers import get_choice_from_env
from paperless.settings.parsers import get_int_from_env
from paperless.settings.parsers import parse_dict_from_str
from paperless.settings.parsers import str_to_bool


class TestStringToBool:
    @pytest.mark.parametrize(
        "true_value",
        [
            pytest.param("true", id="lowercase_true"),
            pytest.param("1", id="digit_1"),
            pytest.param("T", id="capital_T"),
            pytest.param("y", id="lowercase_y"),
            pytest.param("YES", id="uppercase_YES"),
            pytest.param("  True  ", id="whitespace_true"),
        ],
    )
    def test_true_conversion(self, true_value: str):
        """Test that various 'true' strings correctly evaluate to True."""
        assert str_to_bool(true_value) is True

    @pytest.mark.parametrize(
        "false_value",
        [
            pytest.param("false", id="lowercase_false"),
            pytest.param("0", id="digit_0"),
            pytest.param("f", id="capital_f"),
            pytest.param("N", id="capital_N"),
            pytest.param("no", id="lowercase_no"),
            pytest.param("  False  ", id="whitespace_false"),
        ],
    )
    def test_false_conversion(self, false_value: str):
        """Test that various 'false' strings correctly evaluate to False."""
        assert str_to_bool(false_value) is False

    def test_invalid_conversion(self):
        """Test that an invalid string raises a ValueError."""
        with pytest.raises(ValueError, match="Cannot convert 'maybe' to a boolean\\."):
            str_to_bool("maybe")


class TestParseDictFromString:
    def test_empty_and_none_input(self):
        """Test behavior with None or empty string input."""
        assert parse_dict_from_str(None) == {}
        assert parse_dict_from_str("") == {}
        defaults = {"a": 1}
        res = parse_dict_from_str(None, defaults=defaults)
        assert res == defaults
        # Ensure it returns a copy, not the original object
        assert res is not defaults

    def test_basic_parsing(self):
        """Test simple key-value parsing without defaults or types."""
        env_str = "key1=val1, key2=val2"
        expected = {"key1": "val1", "key2": "val2"}
        assert parse_dict_from_str(env_str) == expected

    def test_with_defaults(self):
        """Test that environment values override defaults correctly."""
        defaults = {"host": "localhost", "port": 8000, "user": "default"}
        env_str = "port=9090, host=db.example.com"
        expected = {"host": "db.example.com", "port": "9090", "user": "default"}
        result = parse_dict_from_str(env_str, defaults=defaults)
        assert result == expected

    def test_type_casting(self):
        """Test successful casting of values to specified types."""
        env_str = "port=9090, debug=true, timeout=12.5, user=admin"
        type_map = {"port": int, "debug": bool, "timeout": float}
        expected = {"port": 9090, "debug": True, "timeout": 12.5, "user": "admin"}
        result = parse_dict_from_str(env_str, type_map=type_map)
        assert result == expected

    def test_type_casting_with_defaults(self):
        """Test casting when values come from both defaults and env string."""
        defaults = {"port": 8000, "debug": False, "retries": 3}
        env_str = "port=9090, debug=true"
        type_map = {"port": int, "debug": bool, "retries": int}

        # The 'retries' value comes from defaults and is already an int,
        # so it should not be processed by the caster.
        expected = {"port": 9090, "debug": True, "retries": 3}
        result = parse_dict_from_str(env_str, defaults=defaults, type_map=type_map)
        assert result == expected
        assert isinstance(result["retries"], int)

    def test_path_casting(self, tmp_path: Path):
        """Test successful casting of a string to a resolved pathlib.Path object."""
        # Create a dummy file to resolve against
        test_file = tmp_path / "test_file.txt"
        test_file.touch()

        env_str = f"config_path={test_file}"
        type_map = {"config_path": Path}
        result = parse_dict_from_str(env_str, type_map=type_map)

        # The result should be a resolved Path object
        assert isinstance(result["config_path"], Path)
        assert result["config_path"] == test_file.resolve()

    def test_custom_separator(self):
        """Test parsing with a custom separator like a semicolon."""
        env_str = "host=db; port=5432; user=test"
        expected = {"host": "db", "port": "5432", "user": "test"}
        result = parse_dict_from_str(env_str, separator=";")
        assert result == expected

    def test_edge_cases_in_string(self):
        """Test malformed strings to ensure robustness."""
        # Malformed pair 'debug' is skipped, extra comma is ignored
        env_str = "key=val,, debug, foo=bar"
        expected = {"key": "val", "foo": "bar"}
        assert parse_dict_from_str(env_str) == expected

        # Value can contain the equals sign
        env_str = "url=postgres://user:pass@host:5432/db"
        expected = {"url": "postgres://user:pass@host:5432/db"}
        assert parse_dict_from_str(env_str) == expected

    def test_casting_error_handling(self):
        """Test that a ValueError is raised for invalid casting."""
        env_str = "port=not-a-number"
        type_map = {"port": int}

        with pytest.raises(ValueError) as excinfo:
            parse_dict_from_str(env_str, type_map=type_map)

        assert "Error casting key 'port'" in str(excinfo.value)
        assert "value 'not-a-number'" in str(excinfo.value)
        assert "to type 'int'" in str(excinfo.value)

    def test_bool_casting_error(self):
        """Test that an invalid boolean string raises a ValueError."""
        env_str = "debug=maybe"
        type_map = {"debug": bool}
        with pytest.raises(ValueError, match="Error casting key 'debug'"):
            parse_dict_from_str(env_str, type_map=type_map)

    def test_nested_key_parsing_basic(self):
        """Basic nested key parsing using dot-notation."""
        env_str = "database.host=db.example.com, database.port=5432, logging.level=INFO"
        result = parse_dict_from_str(env_str)
        assert result == {
            "database": {"host": "db.example.com", "port": "5432"},
            "logging": {"level": "INFO"},
        }

    def test_nested_overrides_defaults_and_deepcopy(self):
        """Nested env keys override defaults and defaults are deep-copied."""
        defaults = {"database": {"host": "127.0.0.1", "port": 3306, "user": "default"}}
        env_str = "database.host=db.example.com, debug=true"
        result = parse_dict_from_str(
            env_str,
            defaults=defaults,
            type_map={"debug": bool},
        )

        assert result["database"]["host"] == "db.example.com"
        # Unchanged default preserved
        assert result["database"]["port"] == 3306
        assert result["database"]["user"] == "default"
        # Default object was deep-copied (no same nested object identity)
        assert result is not defaults
        assert result["database"] is not defaults["database"]

    def test_nested_type_casting(self):
        """Type casting for nested keys (dot-notation) should work."""
        env_str = "database.host=db.example.com, database.port=5433, debug=false"
        type_map = {"database.port": int, "debug": bool}
        result = parse_dict_from_str(env_str, type_map=type_map)

        assert result["database"]["host"] == "db.example.com"
        assert result["database"]["port"] == 5433
        assert isinstance(result["database"]["port"], int)
        assert result["debug"] is False
        assert isinstance(result["debug"], bool)

    def test_nested_casting_error_message(self):
        """Error messages should include the full dotted key name on failure."""
        env_str = "database.port=not-a-number"
        type_map = {"database.port": int}
        with pytest.raises(ValueError) as excinfo:
            parse_dict_from_str(env_str, type_map=type_map)

        msg = str(excinfo.value)
        assert "Error casting key 'database.port'" in msg
        assert "value 'not-a-number'" in msg
        assert "to type 'int'" in msg

    def test_type_map_does_not_recast_non_string_defaults(self):
        """If a default already provides a non-string value, the caster should skip it."""
        defaults = {"database": {"port": 3306}}
        type_map = {"database.port": int}
        result = parse_dict_from_str(None, defaults=defaults, type_map=type_map)
        assert result["database"]["port"] == 3306
        assert isinstance(result["database"]["port"], int)


class TestGetIntFromEnv:
    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            pytest.param("42", 42, id="positive"),
            pytest.param("-10", -10, id="negative"),
            pytest.param("0", 0, id="zero"),
            pytest.param("999", 999, id="large_positive"),
            pytest.param("-999", -999, id="large_negative"),
        ],
    )
    def test_existing_env_var_valid_ints(self, mocker, env_value, expected):
        """Test that existing environment variables with valid integers return correct values."""
        mocker.patch.dict(os.environ, {"INT_VAR": env_value})
        assert get_int_from_env("INT_VAR") == expected

    @pytest.mark.parametrize(
        ("default", "expected"),
        [
            pytest.param(100, 100, id="positive_default"),
            pytest.param(0, 0, id="zero_default"),
            pytest.param(-50, -50, id="negative_default"),
            pytest.param(None, None, id="none_default"),
        ],
    )
    def test_missing_env_var_with_defaults(self, mocker, default, expected):
        """Test that missing environment variables return provided defaults."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_int_from_env("MISSING_VAR", default=default) == expected

    def test_missing_env_var_no_default(self, mocker):
        """Test that missing environment variable with no default returns None."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_int_from_env("MISSING_VAR") is None

    @pytest.mark.parametrize(
        "invalid_value",
        [
            pytest.param("not_a_number", id="text"),
            pytest.param("42.5", id="float"),
            pytest.param("42a", id="alpha_suffix"),
            pytest.param("", id="empty"),
            pytest.param(" ", id="whitespace"),
            pytest.param("true", id="boolean"),
            pytest.param("1.0", id="decimal"),
        ],
    )
    def test_invalid_int_values_raise_error(self, mocker, invalid_value):
        """Test that invalid integer values raise ValueError."""
        mocker.patch.dict(os.environ, {"INVALID_INT": invalid_value})
        with pytest.raises(ValueError):
            get_int_from_env("INVALID_INT")


class TestGetEnvChoice:
    @pytest.fixture
    def valid_choices(self) -> set[str]:
        """Fixture providing a set of valid environment choices."""
        return {"development", "staging", "production"}

    def test_returns_valid_env_value(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test that function returns the environment value when it's valid."""
        mocker.patch.dict("os.environ", {"TEST_ENV": "development"})

        result = get_choice_from_env("TEST_ENV", valid_choices)

        assert result == "development"

    def test_returns_default_when_env_not_set(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test that function returns default value when env var is not set."""
        mocker.patch.dict("os.environ", {}, clear=True)

        result = get_choice_from_env("TEST_ENV", valid_choices, default="staging")

        assert result == "staging"

    def test_raises_error_when_env_not_set_and_no_default(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test that function raises ValueError when env var is missing and no default."""
        mocker.patch.dict("os.environ", {}, clear=True)

        with pytest.raises(ValueError) as exc_info:
            get_choice_from_env("TEST_ENV", valid_choices)

        assert "Environment variable 'TEST_ENV' is required but not set" in str(
            exc_info.value,
        )

    def test_raises_error_when_env_value_invalid(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test that function raises ValueError when env value is not in choices."""
        mocker.patch.dict("os.environ", {"TEST_ENV": "invalid_value"})

        with pytest.raises(ValueError) as exc_info:
            get_choice_from_env("TEST_ENV", valid_choices)

        error_msg = str(exc_info.value)
        assert (
            "Environment variable 'TEST_ENV' has invalid value 'invalid_value'"
            in error_msg
        )
        assert "Valid choices are:" in error_msg
        assert "development" in error_msg
        assert "staging" in error_msg
        assert "production" in error_msg

    def test_raises_error_when_default_invalid(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test that function raises ValueError when default value is not in choices."""
        mocker.patch.dict("os.environ", {}, clear=True)

        with pytest.raises(ValueError) as exc_info:
            get_choice_from_env("TEST_ENV", valid_choices, default="invalid_default")

        error_msg = str(exc_info.value)
        assert (
            "Environment variable 'TEST_ENV' has invalid value 'invalid_default'"
            in error_msg
        )

    def test_case_sensitive_validation(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test that validation is case sensitive."""
        mocker.patch.dict("os.environ", {"TEST_ENV": "DEVELOPMENT"})

        with pytest.raises(ValueError):
            get_choice_from_env("TEST_ENV", valid_choices)

    def test_empty_string_env_value(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test behavior with empty string environment value."""
        mocker.patch.dict("os.environ", {"TEST_ENV": ""})

        with pytest.raises(ValueError) as exc_info:
            get_choice_from_env("TEST_ENV", valid_choices)

        assert "has invalid value ''" in str(exc_info.value)

    def test_whitespace_env_value(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test behavior with whitespace-only environment value."""
        mocker.patch.dict("os.environ", {"TEST_ENV": "  development  "})

        with pytest.raises(ValueError):
            get_choice_from_env("TEST_ENV", valid_choices)

    def test_single_choice_set(self, mocker: MockerFixture) -> None:
        """Test function works correctly with single choice set."""
        single_choice: set[str] = {"production"}
        mocker.patch.dict("os.environ", {"TEST_ENV": "production"})

        result = get_choice_from_env("TEST_ENV", single_choice)

        assert result == "production"

    def test_large_choice_set(self, mocker: MockerFixture) -> None:
        """Test function works correctly with large choice set."""
        large_choices: set[str] = {f"option_{i}" for i in range(100)}
        mocker.patch.dict("os.environ", {"TEST_ENV": "option_50"})

        result = get_choice_from_env("TEST_ENV", large_choices)

        assert result == "option_50"

    def test_different_env_keys(
        self,
        mocker: MockerFixture,
        valid_choices: set[str],
    ) -> None:
        """Test function works with different environment variable keys."""
        test_cases = [
            ("DJANGO_ENV", "development"),
            ("DATABASE_BACKEND", "staging"),
            ("LOG_LEVEL", "production"),
            ("APP_MODE", "development"),
        ]

        for env_key, env_value in test_cases:
            mocker.patch.dict("os.environ", {env_key: env_value})
            result = get_choice_from_env(env_key, valid_choices)
            assert result == env_value
