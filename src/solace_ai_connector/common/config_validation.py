"""Utility function for validating configuration dictionaries against a schema."""

from typing import Dict, List, Any
from .log import log


def validate_config_block(
    config_dict: Dict[str, Any], schema_params: List[Dict[str, Any]], log_identifier: str
) -> None:
    """
    Validates a configuration dictionary against a schema definition.

    Checks for required parameters and applies default values based on the schema.
    Modifies the config_dict in place.

    Args:
        config_dict: The configuration dictionary to validate.
        schema_params: A list of dictionaries, where each dictionary defines
                       a parameter schema (e.g., from component 'info' or app 'app_schema').
                       Expected keys in each schema dict: 'name', 'required' (optional, bool),
                       'default' (optional, any).
        log_identifier: A string identifier (e.g., component or app name) for logging messages.

    Raises:
        ValueError: If a required parameter is missing from config_dict.
    """
    if not isinstance(config_dict, dict):
        # This shouldn't happen if called correctly, but good to check.
        log.warning(
            "%s Configuration block provided for validation is not a dictionary (%s). Skipping validation.",
            log_identifier,
            type(config_dict).__name__,
        )
        return

    if not isinstance(schema_params, list):
        log.warning(
            "%s Schema parameters provided for validation is not a list (%s). Skipping validation.",
            log_identifier,
            type(schema_params).__name__,
        )
        return

    for param_schema in schema_params:
        if not isinstance(param_schema, dict):
            log.warning(
                "%s Invalid parameter schema definition (not a dict): %s. Skipping this parameter.",
                log_identifier,
                param_schema,
            )
            continue

        name = param_schema.get("name")
        if not name:
            log.warning(
                "%s Parameter schema definition missing 'name': %s. Skipping this parameter.",
                log_identifier,
                param_schema,
            )
            continue

        required = param_schema.get("required", False)
        default = param_schema.get("default", None) # Use None as sentinel for no default

        # Check if the parameter exists in the configuration
        if name not in config_dict:
            # Check if it's required
            if required:
                raise ValueError(
                    f"{log_identifier}: Required configuration parameter '{name}' is missing."
                )
            # Apply default value if one is defined
            elif default is not None:
                log.debug(
                    "%s Applying default value for parameter '%s': %s",
                    log_identifier,
                    name,
                    default,
                )
                config_dict[name] = default
        # Parameter exists, no action needed regarding required/default checks.
        # Type checking could be added here in the future if desired.

