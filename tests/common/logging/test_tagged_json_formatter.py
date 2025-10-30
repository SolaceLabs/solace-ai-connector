"""
Tests for TaggedJsonFormatter configuration validation.

This module tests the fail-fast validation behavior of TaggedJsonFormatter
to ensure configuration errors raise InitializationError.
"""

import sys
import pytest

sys.path.append("src")

from solace_ai_connector.logging import TaggedJsonFormatter
from solace_ai_connector.common.exceptions import InitializationError


class TestTaggedJsonFormatterValidation:
    """Test suite for TaggedJsonFormatter configuration validation."""

    def test_valid_configuration_with_single_tag(self, monkeypatch):
        """Test that valid configuration with a single tag works correctly."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "SERVICE_NAME")
        monkeypatch.setenv("SERVICE_NAME", "my-service")
        
        formatter = TaggedJsonFormatter()
        
        assert formatter.static_fields == {"SERVICE_NAME": "my-service"}

    def test_valid_configuration_with_multiple_tags(self, monkeypatch):
        """Test that valid configuration with multiple tags works correctly."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "SERVICE_NAME,ENVIRONMENT,VERSION")
        monkeypatch.setenv("SERVICE_NAME", "my-service")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("VERSION", "1.0.0")
        
        formatter = TaggedJsonFormatter()
        
        assert formatter.static_fields == {
            "SERVICE_NAME": "my-service",
            "ENVIRONMENT": "production",
            "VERSION": "1.0.0"
        }

    def test_valid_configuration_with_spaces_around_tags(self, monkeypatch):
        """Test that spaces around tag names are handled correctly."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", " SERVICE_NAME , ENVIRONMENT , VERSION ")
        monkeypatch.setenv("SERVICE_NAME", "my-service")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("VERSION", "1.0.0")
        
        formatter = TaggedJsonFormatter()
        
        assert formatter.static_fields == {
            "SERVICE_NAME": "my-service",
            "ENVIRONMENT": "production",
            "VERSION": "1.0.0"
        }

    def test_valid_env_var_names_with_underscores_and_numbers(self, monkeypatch):
        """Test that valid environment variable names with underscores and numbers work."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "MY_SERVICE_1,_PRIVATE_VAR,VAR_2_TEST")
        monkeypatch.setenv("MY_SERVICE_1", "service1")
        monkeypatch.setenv("_PRIVATE_VAR", "private")
        monkeypatch.setenv("VAR_2_TEST", "test")
        
        formatter = TaggedJsonFormatter()
        
        assert formatter.static_fields == {
            "MY_SERVICE_1": "service1",
            "_PRIVATE_VAR": "private",
            "VAR_2_TEST": "test"
        }

    @pytest.mark.parametrize("tags_value,expected_message", [
        ("", "LOGGING_JSON_TAGS is set but empty"),
        ("   \t\n  ", "LOGGING_JSON_TAGS is set but empty"),
        (",,,", "contains no valid environment variable names"),
    ])
    def test_invalid_logging_json_tags_raises_error(self, monkeypatch, tags_value, expected_message):
        """Test that invalid LOGGING_JSON_TAGS values raise InitializationError."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", tags_value)
        
        with pytest.raises(InitializationError) as exc_info:
            TaggedJsonFormatter()
        
        assert expected_message in str(exc_info.value)

    @pytest.mark.parametrize("invalid_name,additional_check", [
        ("INVALID NAME", "must start with a letter or underscore"),
        ("INVALID-NAME", None),
        ("1INVALID", None),
        ("INVALID@NAME", None),
    ])
    def test_invalid_env_var_name_raises_error(self, monkeypatch, invalid_name, additional_check):
        """Test that invalid environment variable names raise InitializationError."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", invalid_name)
        monkeypatch.setenv(invalid_name, "value")
        
        with pytest.raises(InitializationError) as exc_info:
            TaggedJsonFormatter()
        
        error_message = str(exc_info.value)
        assert f"Invalid environment variable name '{invalid_name}'" in error_message
        if additional_check:
            assert additional_check in error_message

    def test_missing_referenced_env_var_raises_error(self, monkeypatch):
        """Test that missing referenced environment variables raise InitializationError."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "SERVICE_NAME,MISSING_VAR")
        monkeypatch.setenv("SERVICE_NAME", "my-service")
        monkeypatch.delenv("MISSING_VAR", raising=False)
        
        with pytest.raises(InitializationError) as exc_info:
            TaggedJsonFormatter()
        
        assert "Environment variable 'MISSING_VAR' referenced in LOGGING_JSON_TAGS is not set" in str(exc_info.value)
        assert "All environment variables listed in LOGGING_JSON_TAGS must be defined" in str(exc_info.value)

    def test_multiple_missing_env_vars_reports_first_missing(self, monkeypatch):
        """Test that when multiple env vars are missing, the first one is reported."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "VAR1,VAR2,VAR3")
        monkeypatch.delenv("VAR1", raising=False)
        monkeypatch.delenv("VAR2", raising=False)
        monkeypatch.delenv("VAR3", raising=False)
        
        with pytest.raises(InitializationError) as exc_info:
            TaggedJsonFormatter()
        
        assert "Environment variable 'VAR1' referenced in LOGGING_JSON_TAGS is not set" in str(exc_info.value)

    def test_mixed_valid_and_invalid_names_raises_error_on_first_invalid(self, monkeypatch):
        """Test that mixed valid and invalid names raise error on first invalid name."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "VALID_NAME,INVALID-NAME,ANOTHER_VALID")
        monkeypatch.setenv("VALID_NAME", "value1")
        monkeypatch.setenv("INVALID-NAME", "value2")
        monkeypatch.setenv("ANOTHER_VALID", "value3")
        
        with pytest.raises(InitializationError) as exc_info:
            TaggedJsonFormatter()
        
        assert "Invalid environment variable name 'INVALID-NAME'" in str(exc_info.value)

    def test_backward_compatibility_with_service_name_when_logging_json_tags_not_set(self, monkeypatch):
        """Test that SERVICE_NAME fallback works when LOGGING_JSON_TAGS is not set."""
        monkeypatch.delenv("LOGGING_JSON_TAGS", raising=False)
        monkeypatch.setenv("SERVICE_NAME", "legacy-service")
        
        formatter = TaggedJsonFormatter()
        
        assert formatter.static_fields == {"service": "legacy-service"}

    def test_backward_compatibility_with_default_service_name(self, monkeypatch):
        """Test that default SERVICE_NAME is used when neither LOGGING_JSON_TAGS nor SERVICE_NAME is set."""
        monkeypatch.delenv("LOGGING_JSON_TAGS", raising=False)
        monkeypatch.delenv("SERVICE_NAME", raising=False)
        
        formatter = TaggedJsonFormatter()
        
        assert formatter.static_fields == {"service": "solace_agent_mesh"}

    def test_logging_json_tags_takes_precedence_over_service_name(self, monkeypatch):
        """Test that LOGGING_JSON_TAGS takes precedence over SERVICE_NAME when both are set."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "APP_NAME")
        monkeypatch.setenv("APP_NAME", "new-app")
        monkeypatch.setenv("SERVICE_NAME", "legacy-service")
        
        formatter = TaggedJsonFormatter()
        
        # Should use LOGGING_JSON_TAGS, not SERVICE_NAME
        assert formatter.static_fields == {"APP_NAME": "new-app"}
        assert "service" not in formatter.static_fields

    def test_validation_error_messages_are_descriptive(self, monkeypatch):
        """Test that validation error messages provide clear guidance."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "")
        
        with pytest.raises(InitializationError) as exc_info:
            TaggedJsonFormatter()
        
        error_message = str(exc_info.value)
        assert "LOGGING_JSON_TAGS" in error_message
        assert "empty" in error_message.lower()
        assert "provide valid environment variable names" in error_message.lower() or "unset" in error_message.lower()

    def test_case_sensitive_env_var_names(self, monkeypatch):
        """Test that environment variable names are case-sensitive."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "MyService,MYSERVICE")
        monkeypatch.setenv("MyService", "value1")
        monkeypatch.setenv("MYSERVICE", "value2")
        
        formatter = TaggedJsonFormatter()
        
        assert formatter.static_fields == {
            "MyService": "value1",
            "MYSERVICE": "value2"
        }

    def test_empty_env_var_value_is_allowed(self, monkeypatch):
        """Test that empty environment variable values are allowed (only the name must exist)."""
        monkeypatch.setenv("LOGGING_JSON_TAGS", "EMPTY_VAR")
        monkeypatch.setenv("EMPTY_VAR", "")
        
        formatter = TaggedJsonFormatter()
        
        assert formatter.static_fields == {"EMPTY_VAR": ""}
