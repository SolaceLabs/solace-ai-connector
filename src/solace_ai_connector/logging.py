"""
Public logging utilities for the Solace AI Connector.

This module provides user-facing logging components that can be referenced
in logging configuration files.
"""

import os
import re
from pythonjsonlogger.json import JsonFormatter
from .common.exceptions import InitializationError

class TaggedJsonFormatter(JsonFormatter):
    """
    Custom JSON formatter that injects environment variable-based tags into log records.
    
    This formatter extends pythonjsonlogger.jsonlogger.JsonFormatter and automatically
    inject tags from environment variables into JSON log records.
    
    Configuration:
    - LOGGING_JSON_TAGS: Comma-separated list of environment variable names to inject as tags
    - SERVICE_NAME: Legacy environment variable for backward compatibility (deprecated)
    
    Example:
        LOGGING_JSON_TAGS=SERVICE_NAME,ENVIRONMENT,VERSION
        SERVICE_NAME=my-service
        ENVIRONMENT=production
        VERSION=1.0.0
        
        Results in JSON logs with: {..., "SERVICE_NAME": "my-service", "ENVIRONMENT": "production", "VERSION": "1.0.0"}
    """
    
    # Valid environment variable name pattern: starts with letter or underscore, followed by letters, digits, or underscores
    _ENV_VAR_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
    
    def _validate_env_var_name(self, name: str) -> None:
        """
        Validate that an environment variable name follows valid identifier patterns.
        
        Args:
            name: The environment variable name to validate
            
        Raises:
            InitializationError: If the name contains invalid characters or doesn't follow naming rules
        """
        if not self._ENV_VAR_PATTERN.match(name):
            raise InitializationError(
                f"Invalid environment variable name '{name}' in LOGGING_JSON_TAGS. "
                f"Environment variable names must start with a letter or underscore and contain only "
                f"letters, digits, and underscores."
            )
    
    def _validate_logging_json_tags(self, tags_string: str) -> list:
        """
        Validate and parse the LOGGING_JSON_TAGS environment variable value.
        
        Args:
            tags_string: The value of LOGGING_JSON_TAGS environment variable
            
        Returns:
            List of validated tag names
            
        Raises:
            InitializationError: If the configuration is invalid (empty, invalid names, or missing env vars)
        """
        # Check if the string is empty or only whitespace
        if not tags_string.strip():
            raise InitializationError(
                "LOGGING_JSON_TAGS is set but empty. Either provide valid environment variable names or unset LOGGING_JSON_TAGS."
            )
        
        # Parse and validate tag names
        tag_names = [tag.strip() for tag in tags_string.split(",") if tag.strip()]
        
        if not tag_names:
            raise InitializationError(
                "LOGGING_JSON_TAGS is set but contains no valid environment variable names. "
                "Either provide valid environment variable names or unset LOGGING_JSON_TAGS."
            )
        
        # Validate each tag name
        for tag_name in tag_names:
            self._validate_env_var_name(tag_name)
            
            # Check if the referenced environment variable exists
            if os.getenv(tag_name) is None:
                raise InitializationError(
                    f"Environment variable '{tag_name}' referenced in LOGGING_JSON_TAGS is not set. "
                    f"All environment variables listed in LOGGING_JSON_TAGS must be defined."
                )
        
        return tag_names
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the formatter
        
        Behavior:
        1. If LOGGING_JSON_TAGS is set: validate and parse tags, then add as defaults on superclass
        2. If LOGGING_JSON_TAGS is not set but SERVICE_NAME is: use SERVICE_NAME with deprecation warning
        3. Raise InitializationError on invalid configuration
        """
        super().__init__(*args, **kwargs)
        tags = {}

        logging_json_tags = os.getenv("LOGGING_JSON_TAGS")
        
        if logging_json_tags is not None:
            # Validate and parse LOGGING_JSON_TAGS
            tag_names = self._validate_logging_json_tags(logging_json_tags)
            
            # Add validated tags to the tags dictionary
            for tag_name in tag_names:
                tag_value = os.getenv(tag_name)
                # At this point, we know the env var exists due to validation
                tags[tag_name] = tag_value

        else:
            # LOGGING_JSON_TAGS not set - check for backward compatibility with SERVICE_NAME
            service_name = os.getenv("SERVICE_NAME", "solace_agent_mesh")
            tags["service"] = service_name # Legacy support; prefer LOGGING_JSON_TAGS

        # Set defaults in superclass https://nhairs.github.io/python-json-logger/latest/quickstart/#default-fields
        self.static_fields = tags
