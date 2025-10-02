"""Random utility functions"""

import logging
import importlib.util
import os
import sys
import re
import builtins
import subprocess
import types
import base64
import gzip
import json
import yaml
import unicodedata
from copy import deepcopy
from collections.abc import Mapping

log = logging.getLogger(__name__)

def import_from_directories(module_name, base_path=None):
    dirs = sys.path
    if base_path:
        dirs.append(base_path)
    for path in dirs:
        dirs = [path]
        dirs.extend(get_subdirectories(path))
        for directory in dirs:
            ## Skip if __pycache__ or .git
            if directory.endswith("__pycache__") or directory.endswith(".git"):
                continue
            module_file = module_name
            if "." in module_name:
                module_file = module_name.replace(".", os.sep)
            module_path = os.path.join(directory, module_file + ".py")
            if os.path.exists(module_path):
                try:
                    # if module_path.startswith("src/solace_ai_connector"):
                    if "/solace_ai_connector/" in module_path:
                        # Remove everything up to and including src/
                        module_name = re.sub(
                            r".*/solace_ai_connector/",
                            "solace_ai_connector/",
                            module_path,
                        )
                        module_name = module_name.replace("/", ".")
                        if module_name.endswith(".py"):
                            module_name = module_name[:-3]
                    spec = importlib.util.spec_from_file_location(
                        module_name, module_path
                    )
                    module = importlib.util.module_from_spec(spec)
                    # Insert this module's directory into sys.path so that it
                    # can import other modules
                    if path not in sys.path:
                        sys.path.insert(0, path)
                    spec.loader.exec_module(module)
                except Exception:
                    log.exception("Exception importing %s", module_path)
                    raise ValueError(
                        f"Error importing module {module_path} - {module_name}"
                    ) from None
                return module
    raise ImportError(f"Could not import module '{module_name}'") from None


def get_subdirectories(path=None):
    subdirectories = []
    for dirpath, dirnames, _ in os.walk(path):
        subdirectories.extend([os.path.join(dirpath, name) for name in dirnames])
    return subdirectories


def resolve_config_values(config, allow_source_expression=False):
    """Resolve any config module values in the config by processing 'invoke' entries"""
    # log.debug("Resolving config values in %s", config)
    if not isinstance(config, (dict, list)):
        return config
    if isinstance(config, list):
        for index, item in enumerate(config):
            if isinstance(item, dict):
                config[index] = resolve_config_values(item, allow_source_expression)
        return config
    if "invoke" in config:
        # First resolve any config module values in the invoke config
        resolve_config_values(config["invoke"], allow_source_expression)
        config = invoke_config(config["invoke"], allow_source_expression)
        log.debug("Resolved config value to %s", config)
        return config
    for key, value in config.items():
        # If the key is source_expression, we sub config to use the 'evaluate_expression()' value in
        # invoke parameters
        config[key] = resolve_config_values(
            value,
            allow_source_expression=allow_source_expression
            or key == "source_value"
            or key == "source_expression"
            or key == "component_processing",
        )
    return config


def import_module(module, base_path=None, component_package=None):
    """
    Import a module by name or return the module object if it's already imported.
    
    Args:
        module: Module name as string or an already imported module object
        base_path: Optional base path to add to sys.path
        component_package: Optional package to install if needed
        
    Returns:
        The imported module object
        
    Raises:
        ModuleNotFoundError: If the module cannot be found
        ImportError: If there's an error during module import
    """
    # If already a module object, return it directly
    if isinstance(module, types.ModuleType):
        return module

    # Install package if specified
    if component_package:
        install_package(component_package)

    # Add base path to sys.path if provided
    if base_path and base_path not in sys.path:
        sys.path.append(base_path)
        
    # Try direct import first
    try:
        return importlib.import_module(module)
    except ModuleNotFoundError as original_error:
        # For modules without dots, try known prefixes
        if "." not in module:
            imported_module = _try_import_from_known_prefixes(module, original_error)
            if imported_module:
                return imported_module
                
        # If we get here, the module wasn't found
        raise ModuleNotFoundError(f"Module '{module}' not found") from original_error

def _try_import_from_known_prefixes(module_name, original_error):
    """
    Try to import a module from known prefixes.
    
    Args:
        module_name: The base module name to import
        original_error: The original ModuleNotFoundError
        
    Returns:
        The imported module if successful, None otherwise
    """
    # Known prefix combinations to try
    prefix_prefixes = ["solace_ai_connector", "."]
    prefixes = [
        ".components",
        ".components.general",
        ".components.general.for_testing",
        ".components.general.llm.langchain",
        ".components.general.llm.openai",
        ".components.general.llm.litellm",
        ".components.general.db.mongo",
        ".components.general.db.sql",
        ".components.general.websearch",
        ".components.inputs_outputs",
        ".transforms",
        ".common",
    ]
    
    # Try each combination of prefixes
    for prefix_prefix in prefix_prefixes:
        for prefix in prefixes:
            full_name = f"{prefix_prefix}{prefix}.{module_name}"
            try:
                # Handle relative imports differently
                if full_name.startswith("."):
                    return importlib.import_module(full_name, package=__package__)
                else:
                    return importlib.import_module(full_name)
            except ModuleNotFoundError as e:
                # Skip if this is clearly not the right module
                name = str(e.name)
                if (name != "solace_ai_connector" and
                    name.split(".")[-1] != full_name.split(".")[-1]):
                    continue
            except Exception:
                # For other exceptions, provide a helpful error message
                raise ImportError(
                    f"Module load error for {full_name}. Please ensure that all required "
                    f"dependencies are installed and parameters are correct. "
                    f"Error: {str(original_error)}"
                ) from None
    
    # If we get here, the module wasn't found in any of the known prefixes
    return None


def invoke_config(config, allow_source_expression=False):
    """Invoke a section of the config. The config can be one of the following:
    1. module: the name of the module to import. This will then be treated as an object
    2. object: an object to call a function or retrieve an attribute from
      a. attribute: an attribute of that object
      b. function: a function to call on that object (takes params)
    3. function: just a plain function to call (takes params)

    If any parameters are a source expression, make sure that is allowed and if it is
    we need to return a lambda function that will call the source expression when invoked.
    If any parameters are a function, then we need to return a lambda function that will call
    the function when invoked.
    """
    path = config.get("path")
    module = config.get("module")
    obj = config.get("object")
    attribute = config.get("attribute")
    function = config.get("function")
    params = config.get("params", {})

    if module and obj:
        raise ValueError(
            "Cannot have both module and object in an 'invoke' config"
        ) from None

    if module:
        obj = import_module(module, base_path=path)

    if obj:
        if attribute:
            return getattr(obj, attribute)
        if function:
            func = getattr(obj, function)
            return call_function(func, params, allow_source_expression)

    if function:
        func = globals().get(function)
        if func is None:
            func = getattr(builtins, function, None)
            if func is None:
                raise ValueError(
                    f"Function '{function}' not a known python function"
                ) from None
        return call_function(func, params, allow_source_expression)


def call_function(function, params, allow_source_expression):
    """Call a function with parameters. Note that there are several ways to pass parameters:
    1. positional: a list of positional parameters
    2. keyword: a dictionary of keyword parameters
    3. a dictionary of parameters
    4. no parameters
    """
    positional = params.get("positional")
    keyword = params.get("keyword")
    if positional is not None and not isinstance(positional, list):
        raise ValueError("positional must be a list") from None
    if keyword is not None and not isinstance(keyword, dict):
        raise ValueError("keyword must be a dict") from None

    # Loop through the parameters looking for source expressions and lambda functions
    have_lambda = False
    if positional:
        for index, value in enumerate(positional):
            # source_expression check for backwards compatibility
            if isinstance(value, str) and (
                value.startswith("evaluate_expression(")
                or value.startswith("source_expression(")
            ):
                (expression, data_type) = extract_evaluate_expression(value)
                positional[index] = create_lambda_function_for_source_expression(
                    expression, data_type=data_type
                )
                have_lambda = True
            elif callable(value):
                have_lambda = True
    if keyword:
        for key, value in keyword.items():
            # source_expression check for backwards compatibility
            if isinstance(value, str) and (
                value.startswith("evaluate_expression(")
                or value.startswith("source_expression(")
            ):
                if not allow_source_expression:
                    raise ValueError(
                        "evaluate_expression() is not allowed in this context"
                    ) from None
                (expression, data_type) = extract_evaluate_expression(value)
                keyword[key] = create_lambda_function_for_source_expression(
                    expression, data_type=data_type
                )
                have_lambda = True
            elif callable(value):
                have_lambda = True
    if have_lambda:
        return lambda message: call_function_with_params(
            message, function, positional, keyword
        )

    if positional and keyword:
        return function(*positional, **keyword)
    if positional:
        return function(*positional)
    if keyword:
        return function(**keyword)
    return function(**params)


def install_package(package_name):
    """Install a package using pip if it isn't already installed"""
    try:
        importlib.import_module(package_name)
    except ImportError:
        subprocess.run(["pip", "install", package_name], check=True)


def extract_evaluate_expression(se_call):
    # First remove the evaluate_expression( and the trailing )
    # Account for possible whitespace
    if se_call.startswith("evaluate_expression("):
        expression = se_call.split("evaluate_expression(")[1].split(")")[0].strip()
    else:
        # For backwards compatibility
        expression = se_call.split("source_expression(")[1].split(")")[0].strip()
    data_type = None
    if "," in expression:
        (expression, data_type) = re.split(r"\s*,\s*", expression)

    if not expression:
        raise ValueError("evaluate_expression() must contain an expression") from None
    return (expression, data_type)


def call_function_with_params(message, function, positional, keyword):
    # First we need to call any lambda functions to get the actual parameters
    if positional:
        positional = positional.copy()
        for index, value in enumerate(positional):
            if callable(value):
                positional[index] = value(message)
    if keyword:
        keyword = keyword.copy()
        for key, value in keyword.items():
            if callable(value):
                keyword[key] = value(message)
    if positional and keyword:
        return function(*positional, **keyword)
    if positional:
        return function(*positional)
    if keyword:
        return function(**keyword)
    return function()


def create_lambda_function_for_source_expression(source_expression, data_type=None):
    """Create a lambda function that will call the source expression when invoked"""
    return lambda message: message.get_data(source_expression, data_type=data_type)


def get_source_expression(config_obj, key="source_expression"):
    if "source_value" in config_obj:
        source_value = config_obj.get("source_value")
        if callable(source_value) or isinstance(source_value, (dict, list)):
            return source_value
        return "static:" + str(source_value)
    return config_obj.get(key, None)


def get_obj_text(block_format, text):
    """Extract the text of the object in the specified format. It simply
    looks for a ```<format> key"""
    # if ```<format> is in the text, get all text between that and the next ```
    if f"```{block_format}" in text:
        return text.split(f"```{block_format}")[1].split("```")[0]
    return text


def ensure_slash_on_end(string):
    if not string:
        return ""
    if not string.endswith("/"):
        return string + "/"
    return string


def ensure_slash_on_start(string):
    if not string:
        return ""
    if not string.startswith("/"):
        return "/" + string
    return string


def encode_payload(payload, encoding, payload_format):
    # First, format the payload
    if payload_format == "json":
        formatted_payload = json.dumps(payload)
    elif payload_format == "yaml":
        formatted_payload = yaml.dump(payload)
    elif isinstance(payload, bytes) or isinstance(payload, bytearray):
        formatted_payload = payload
    else:
        formatted_payload = str(payload)

    # Then, encode the formatted payload
    if encoding == "utf-8":
        # Ensure it's bytes before returning
        if isinstance(formatted_payload, str):
            return formatted_payload.encode("utf-8")
        return formatted_payload  # Already bytes/bytearray
    elif encoding == "base64":
        if isinstance(formatted_payload, str):
            formatted_payload = formatted_payload.encode("utf-8")
        return base64.b64encode(formatted_payload)
    elif encoding == "gzip":
        if isinstance(formatted_payload, str):
            formatted_payload = formatted_payload.encode("utf-8")
        return gzip.compress(formatted_payload)
    else:  # Includes 'none' encoding
        return formatted_payload


def clean_json_string(json_str):
    """Clean a JSON string by removing or replacing invalid control characters
    and properly escaping unescaped newlines within string values"""
    if not isinstance(json_str, str):
        return json_str
    
    # Remove or replace problematic control characters while preserving valid JSON content
    # Keep printable characters and valid whitespace
    cleaned = ""
    in_string = False  # Track if we're inside a JSON string value
    escape_next = False  # Track if the next character is escaped
    
    for char in json_str:
        # Handle string context tracking
        if char == '"' and not escape_next:
            in_string = not in_string
            cleaned += char
            continue
        
        # Handle escape sequences
        if char == '\\' and not escape_next:
            escape_next = True
            cleaned += char
            continue
        
        if escape_next:
            cleaned += char
            escape_next = False
            continue
        
        # Inside strings, handle newlines and control characters specially
        if in_string:
            if char == '\n':
                # Properly escape newlines in string values for valid JSON
                cleaned += ' '
            elif char == '\r':
                # Properly escape carriage returns in string values
                cleaned += ' '
            elif char == '\t':
                # Properly escape tabs in string values
                cleaned += ' '
            elif char.isprintable() or char == ' ':
                # Keep other printable characters and spaces as-is
                cleaned += char
            else:
                # For non-printable control characters inside strings, replace with space
                category = unicodedata.category(char)
                if category.startswith('C'):
                    # Replace problematic control chars with space, but avoid double spaces
                    if cleaned and cleaned[-1] != ' ':
                        cleaned += ' '
                else:
                    cleaned += char
        else:
            # Outside strings, keep valid JSON structural characters and whitespace as-is
            if char.isprintable() or char in ['\t', '\n', '\r', ' ']:
                cleaned += char
            # Skip other control characters outside strings
    
    return cleaned


def decode_payload(payload, encoding, payload_format):
    decoded_payload = payload  # Start with original payload

    # --- Decoding based on 'encoding' ---
    if encoding == "base64":
        try:
            # Ensure payload is bytes before decoding base64
            if isinstance(payload, str):
                payload = payload.encode("ascii")  # Base64 is ASCII
            decoded_payload = base64.b64decode(payload)
        except Exception:
            log.exception("Error decoding base64 payload")
            raise ValueError("Error decoding base64 payload") from None
    elif encoding == "gzip":
        try:
            # Ensure payload is bytes before decompressing
            if not isinstance(payload, (bytes, bytearray)):
                raise TypeError("Gzip payload must be bytes or bytearray")
            decoded_payload = gzip.decompress(payload)
        except Exception:
            log.exception("Error decompressing gzip payload")
            raise ValueError("Error decompressing gzip payload") from None
    # If encoding is utf-8, unicode_escape, or potentially others,
    # the result should be a string for further format parsing (JSON/YAML).
    # If the payload is already bytes/bytearray, decode it.
    elif isinstance(payload, (bytes, bytearray)):
        try:
            if encoding == "utf-8":
                decoded_payload = payload.decode("utf-8")
            elif encoding == "unicode_escape":
                decoded_payload = payload.decode("unicode_escape")
            # Add other encodings if needed
            # else: if encoding is 'none' or unknown, keep as bytes? Or try utf-8?
            # For now, assume if it's bytes and encoding isn't handled above, it remains bytes
            # unless format requires string. Let's default to trying utf-8 for string formats.
            elif payload_format in ["json", "yaml", "text"]:
                try:
                    decoded_payload = payload.decode("utf-8")
                    log.debug(
                        "Payload was bytes, decoded as utf-8 for format %s",
                        payload_format,
                    )
                except UnicodeDecodeError:
                    log.warning(
                        "Could not decode bytes payload as utf-8 for format %s, leaving as bytes.",
                        payload_format,
                    )
                    # Keep decoded_payload as original bytes if utf-8 fails

        except UnicodeDecodeError:
            log.exception("Error decoding payload with encoding '%s'.", encoding)
            # Decide how to handle - raise error or return raw bytes?
            # Returning raw bytes might be safer if subsequent steps can handle it.
            # For now, let's keep decoded_payload as the original bytes.
        except Exception:
            log.exception(
                "Unexpected error during payload decoding with encoding '%s'.",
                encoding,
            )
            raise ValueError(
                f"Unexpected error during payload decoding with encoding '{encoding}'"
            ) from None

    # --- Parsing based on 'payload_format' ---
    # This step expects decoded_payload to be a string for JSON/YAML
    if payload_format == "json":
        if isinstance(decoded_payload, (bytes, bytearray)):
            # Attempt to decode as utf-8 if it's still bytes
            try:
                decoded_payload = decoded_payload.decode("utf-8")
            except UnicodeDecodeError:
                log.exception(
                    "Cannot parse JSON, payload is bytes and not valid utf-8."
                )
                raise ValueError(
                    "Invalid payload for JSON format: not valid utf-8 bytes"
                ) from None

        if isinstance(decoded_payload, str):
            try:
                return json.loads(decoded_payload)
            except Exception as e:
                try:
                    log.warning(
                        "Error decoding JSON payload string, trying to clean it up"
                    )
                    cleaned_payload = clean_json_string(decoded_payload)
                    return json.loads(cleaned_payload)
                except Exception as e:
                    log.exception(f"Unexpected error decoding JSON payload: {e}")
                    log.info("Payload content: %s", payload)
                    raise ValueError("Invalid JSON payload") from e
        else:
            # If it wasn't bytes or string, it might already be parsed (e.g., from dev broker)
            return decoded_payload

    elif payload_format == "yaml":
        if isinstance(decoded_payload, (bytes, bytearray)):
            # Attempt to decode as utf-8 if it's still bytes
            try:
                decoded_payload = decoded_payload.decode("utf-8")
            except UnicodeDecodeError:
                log.exception(
                    "Cannot parse YAML, payload is bytes and not valid utf-8."
                )
                raise ValueError(
                    "Invalid payload for YAML format: not valid utf-8 bytes"
                ) from None

        if isinstance(decoded_payload, str):
            try:
                return yaml.safe_load(decoded_payload)
            except Exception:  # Catches YAML parsing errors
                log.exception("Error decoding YAML payload string")
                raise ValueError("Invalid YAML payload") from None
        else:
            # If it wasn't bytes or string, it might already be parsed
            return decoded_payload

    # If format is 'text' or 'none' or unknown, return the decoded_payload as is
    # (which could be string, bytes, or already parsed object)
    return decoded_payload


def get_data_value(data_object, expression, resolve_none_colon=False):
    # If the data_object is a value, return it
    if (
        not isinstance(data_object, dict)
        and not isinstance(data_object, list)
        and not isinstance(data_object, object)
    ):
        return data_object

    if ":" not in expression:
        if resolve_none_colon:
            return (data_object or {}).get(expression)
        else:
            return data_object

    data_name = expression.split(":")[1]

    if data_name == "":
        return data_object

    # Split the data_name by dots to get the path
    path_parts = data_name.split(".")

    # Start with the entire data_object
    current_data = data_object

    # Traverse the path
    for part in path_parts:
        # If the current data is a dictionary, get the value with the key 'part'
        if isinstance(current_data, dict):
            current_data = current_data.get(part)
        # If the current data is a list and 'part' is a number, get the value at
        # the index 'part'
        elif isinstance(current_data, list) and part.isdigit():
            try:
                current_data = current_data[int(part)]
            except IndexError:
                current_data = None  # Index out of bounds
        # If the current data is neither a dictionary nor a list, or if 'part' is
        # not a number, return None
        elif isinstance(current_data, object):
            current_data = getattr(current_data, part, None)
        else:
            # This case means current_data is a scalar (str, int, etc.) but path continues
            log.error(
                f"Cannot access part '{part}' of a non-collection type "
                f"({type(current_data)}) in expression '{expression}'"
            )
            raise ValueError(
                f"Cannot access part '{part}' of a non-collection type "
                f"({type(current_data)}) in expression '{expression}'"
            ) from None

        # If at any point we get None, stop and return None
        if current_data is None:
            return None

    # Return the final data
    return current_data


# Similar to get_data_value, we need to use the expression to find the place to set the value
# except that we will create objects along the way if they don't exist
def set_data_value(data_object, expression, value):
    if ":" not in expression:
        # Handle case where data_object might not be a dict initially
        if isinstance(data_object, dict):
            data_object[expression] = value
        # Add handling for lists if needed, otherwise raise error or ignore
        else:
            log.warning(
                f"Cannot set key '{expression}' on non-dict object: {type(data_object)}"
            )
        return

    data_name = expression.split(":")[1]

    # It is an error if the data_object is None
    if data_object is None:
        raise ValueError(
            f"Could not set data value for expression '{expression}' - data_object is None"
        ) from None
    # Allow setting on non-dict/list if path is empty? No, require container.
    if not isinstance(data_object, (dict, list)):
        raise ValueError(
            f"Could not set data value for expression '{expression}' - data_object "
            f"is not a dictionary or list, but a {type(data_object)}"
        ) from None

    # It is an error if the data_name is empty
    if data_name == "":
        raise ValueError(
            f"Could not set data value for expression '{expression}' - data_name is empty"
        ) from None

    # Split the data_name by dots to get the path
    path_parts = data_name.split(".")

    # Start with the entire data_object
    current_data = data_object

    # Traverse the path
    for i, part in enumerate(path_parts):
        is_last_part = i == len(path_parts) - 1
        next_part_is_digit = not is_last_part and path_parts[i + 1].isdigit()

        if isinstance(current_data, dict):
            if is_last_part:
                current_data[part] = value
            else:
                # Ensure the next level exists and is the correct type (dict or list)
                if part not in current_data or not isinstance(
                    current_data[part], (dict, list)
                ):
                    current_data[part] = [] if next_part_is_digit else {}
                elif next_part_is_digit and not isinstance(current_data[part], list):
                    log.warning(
                        f"Overwriting non-list with list at '{'.'.join(path_parts[:i+1])}' in expression '{expression}'"
                    )
                    current_data[part] = []
                elif not next_part_is_digit and not isinstance(
                    current_data[part], dict
                ):
                    log.warning(
                        f"Overwriting non-dict with dict at '{'.'.join(path_parts[:i+1])}' in expression '{expression}'"
                    )
                    current_data[part] = {}
                current_data = current_data[part]

        elif isinstance(current_data, list) and part.isdigit():
            idx = int(part)
            # Ensure list is long enough
            while len(current_data) <= idx:
                current_data.append(None)

            if is_last_part:
                current_data[idx] = value
            else:
                # Ensure the element at idx exists and is the correct type
                if current_data[idx] is None or not isinstance(
                    current_data[idx], (dict, list)
                ):
                    current_data[idx] = [] if next_part_is_digit else {}
                elif next_part_is_digit and not isinstance(current_data[idx], list):
                    log.warning(
                        f"Overwriting non-list with list at index {idx} of '{'.'.join(path_parts[:i])}' in expression '{expression}'"
                    )
                    current_data[idx] = []
                elif not next_part_is_digit and not isinstance(current_data[idx], dict):
                    log.warning(
                        f"Overwriting non-dict with dict at index {idx} of '{'.'.join(path_parts[:i])}' in expression '{expression}'"
                    )
                    current_data[idx] = {}
                current_data = current_data[idx]
        else:
            # Current data is not a container type we can traverse/set into
            raise TypeError(
                f"Cannot traverse or set part '{part}' in expression '{expression}'. "
                f"Encountered non-container type {type(current_data)} at path '{'.'.join(path_parts[:i])}'"
            )


def remove_data_value(data_object, expression):
    if ":" not in expression:
        if isinstance(data_object, dict):
            data_object.pop(expression, None)
        # Add handling for lists if needed
        return

    data_name = expression.split(":")[1]

    # Allow removing from None or non-containers? No, should raise error or log.
    if data_object is None:
        raise ValueError(
            f"Could not remove data value for expression '{expression}' - data_object is None"
        ) from None
    if not isinstance(data_object, dict) and not isinstance(data_object, list):
        raise ValueError(
            f"Could not remove data value for expression '{expression}' - data_object "
            "is not a dictionary or list"
        ) from None

    # It is an error if the data_name is empty
    if data_name == "":
        raise ValueError(
            f"Could not remove data value for expression '{expression}' - data_name is empty"
        ) from None

    path_parts = data_name.split(".")
    current_data = data_object

    # Traverse the path up to the second-to-last part
    for i, part in enumerate(path_parts[:-1]):
        if isinstance(current_data, dict):
            current_data = current_data.get(part)
        elif isinstance(current_data, list) and part.isdigit():
            try:
                current_data = current_data[int(part)]
            except IndexError:
                current_data = None
        else:
            current_data = None  # Cannot traverse further

        if current_data is None:
            log.debug(
                f"Path does not exist for removal: '{expression}' at part '{part}'"
            )
            return  # Path doesn't exist, nothing to remove

    # Handle the last part
    last_part = path_parts[-1]
    if isinstance(current_data, dict):
        current_data.pop(last_part, None)
    elif isinstance(current_data, list) and last_part.isdigit():
        idx = int(last_part)
        if 0 <= idx < len(current_data):
            # Decide whether to pop or set to None. Popping changes indices. Setting to None might be safer.
            # Let's pop for now, consistent with dict behavior.
            current_data.pop(idx)
        else:
            if isinstance(current_data, dict):
                current_data = current_data.get(part, {})
            elif isinstance(current_data, list) and part.isdigit():
                if len(current_data) > int(part):
                    current_data = current_data[int(part)]
            else:
                log.error(
                    "Could not remove data value for expression '%s' - data "
                    "is not a dictionary or list",
                    expression,
                )


def deep_merge(d, u):
    # Create a deep copy of first dict to avoid modifying original
    result = deepcopy(d)

    # Iterate through keys and values in second dict
    for k, v in u.items():
        if k in result:
            # If key exists in both dicts
            if isinstance(result[k], list) and isinstance(v, list):
                # For lists: extend the existing list
                result[k].extend(v)
            elif isinstance(result[k], Mapping) and isinstance(v, Mapping):
                # For nested dicts: recursive merge
                result[k] = deep_merge(result[k], v)
            else:
                # For other types: replace value
                result[k] = v
        else:
            # Otherwise, destination value replaces source value (including replacing list with non-list, etc.)
            result[k] = deepcopy(v)
    return result
