# Implementation Plan: App Configuration Schema and Validation

**Goal:** Add the ability to define a schema for the `app_config` block within `App` definitions (both base and custom subclasses) and validate the provided configuration against this schema during app initialization. This mirrors the existing validation mechanism for components.

**Key Principles:**

*   **Consistency:** Use the same schema structure (`config_parameters` list) as components.
*   **DRY:** Extract common validation logic into a reusable utility function.
*   **Backward Compatibility:** Apps without a defined schema should continue to work without validation.
*   **Clarity:** Schema definition should be clearly associated with the `App` class.
*   **Early Failure:** Validation should occur during app initialization.

**Implementation Steps:**

1.  **Create Configuration Validation Utility Function:**
    *   **Location:** Create a new file `src/solace_ai_connector/common/config_validation.py` or add to `src/solace_ai_connector/common/utils.py`.
    *   **Function Signature:** `def validate_config_block(config_dict: dict, schema_params: list, log_identifier: str) -> None:`
    *   **Logic:**
        *   Iterate through `schema_params` (list of parameter definition dictionaries).
        *   For each parameter definition:
            *   Get `name`, `required` (default `False`), `default` (default `None`).
            *   Check if `name` exists in `config_dict`.
            *   If `required` is `True` and `name` is not in `config_dict`, raise `ValueError` with a clear message including `log_identifier`.
            *   If `name` is not in `config_dict` and `default` is not `None`, add the default value to `config_dict[name]`.
        *   The function modifies `config_dict` in place.
    *   **Logging:** Use `log.warning` or `log.debug` for informational messages (e.g., applying defaults).

2.  **Refactor `ComponentBase.validate_config`:**
    *   **File:** `src/solace_ai_connector/components/component_base.py`
    *   **Modification:**
        *   Import the new `validate_config_block` function.
        *   Replace the existing loop and validation logic within `validate_config` with a call to `validate_config_block`.
        *   Pass `self.component_config`, `config_params` (extracted from `self.module_info`), and `self.log_identifier` to the utility function.
        *   ```python
          # Inside ComponentBase.validate_config
          from ..common.config_validation import validate_config_block # Or from ..common.utils

          config_params = self.module_info.get("config_parameters", [])
          if config_params: # Only validate if schema exists
              try:
                  validate_config_block(
                      self.component_config,
                      config_params,
                      self.log_identifier
                  )
              except ValueError as e:
                  # Re-raise or handle appropriately, maybe add more context
                  raise ValueError(f"Configuration error in component '{self.name}': {e}") from e
          ```

3.  **Modify `App` Class:**
    *   **File:** `src/solace_ai_connector/flow/app.py`
    *   **Add `app_schema` Class Attribute:**
        *   Define `app_schema = {"config_parameters": []}` at the class level of `App`. This allows base `App` to potentially define its own parameters later and provides a standard place for subclasses to define theirs.
    *   **Implement `_validate_app_config` Method:**
        *   ```python
          # Inside App class
          from ..common.config_validation import validate_config_block # Or from ..common.utils

          def _validate_app_config(self):
              """Validates self.app_config against the class's app_schema."""
              schema = getattr(self.__class__, "app_schema", None)
              if schema and isinstance(schema, dict):
                  schema_params = schema.get("config_parameters", [])
                  if schema_params and isinstance(schema_params, list):
                      log.debug("Validating app_config for app '%s' against schema.", self.name)
                      try:
                          # Validate self.app_config which holds the merged app-level config block
                          validate_config_block(
                              self.app_config,
                              schema_params,
                              f"App '{self.name}'"
                          )
                      except ValueError as e:
                          # Re-raise with context
                          raise ValueError(f"Configuration error in app '{self.name}': {e}") from e
                  else:
                      log.debug("No 'config_parameters' found in app_schema for app '%s'. Skipping validation.", self.name)
              else:
                  log.debug("No app_schema defined for app class '%s'. Skipping validation.", self.__class__.__name__)
          ```
    *   **Call Validation in `__init__`:**
        *   Locate the point in `App.__init__` *after* `merged_app_info` is created, `resolve_config_values` is called on it, and `self.app_config` is extracted from `merged_app_info.get("app_config", {})`.
        *   Insert the call: `self._validate_app_config()`
        *   Ensure this happens before any logic that might *rely* on validated/defaulted `app_config` values.

4.  **Update Documentation:**
    *   **File:** `docs/configuration.md` (or potentially a new `docs/apps.md`)
        *   Explain the `app_config` section within an app definition.
        *   Document how to define an `app_schema` (with `config_parameters`) in custom `App` subclasses to enable validation and default values for `app_config`.
        *   Provide an example of a custom `App` class with `app_schema`.
        *   Clarify that validation only occurs if `app_schema` with `config_parameters` is defined.
    *   **File:** `docs/custom_components.md` (or similar)
        *   Briefly mention that custom `App` classes can define `app_schema` for configuration validation.

5.  **Add Tests:**
    *   **Location:** Create a new test file, e.g., `tests/unit/test_app_validation.py`.
    *   **Test Cases:**
        *   Test `validate_config_block` directly with various schemas and config dictionaries (missing required, present optional, default application).
        *   Test `App.__init__` with a custom `App` subclass that *has* an `app_schema`:
            *   Test successful validation with correct config.
            *   Test application of default values from the schema.
            *   Test `ValueError` raised when a required parameter is missing from `app_config`.
        *   Test `App.__init__` with a custom `App` subclass that *does not* have `app_schema` (or has an empty one) - ensure no validation error occurs even with arbitrary `app_config`.
        *   Test `App.__init__` using the base `App` class with a YAML config containing `app_config` - ensure no validation error occurs (as base `App` has no schema parameters by default).

**Review Notes:**

*   Consider the exact placement of the `validate_config_block` function (new file vs. `utils.py`). A new file might be cleaner.
*   Ensure error messages from `validate_config_block` and the calling methods (`App._validate_app_config`, `ComponentBase.validate_config`) provide sufficient context (app/component name).
*   Double-check the timing of the `_validate_app_config()` call within `App.__init__` relative to config merging and resolution.
