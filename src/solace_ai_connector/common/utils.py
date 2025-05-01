"""Random utility functions"""

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
from copy import deepcopy
from collections.abc import Mapping

from .log import log


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
                    log.error("Exception importing %s", module_path)
                    raise ValueError(
                        f"Error importing module {module_path} - {module_name}"
                    ) from None
                return module
    raise ImportError(f"Could not import module '{module_name}'") from None


def get_subdirectories(path=None):
    # script_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # directory = os.curdir
    # if path:
    #     directory = path
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
    """Import a module by name or return the module object if it's already imported"""

    if isinstance(module, types.ModuleType):
        return module

    if component_package:
        install_package(component_package)

    if base_path:
        if base_path not in sys.path:
            sys.path.append(base_path)
    try:
        return importlib.import_module(module)
    except ModuleNotFoundError:
        # If the module does not have a path associated with it, try
        # importing it from the known prefixes - annoying that this
        # is necessary. It seems you can't dynamically import a module
        # that is listed in an __init__.py file :(
        if "." not in module:
            for prefix_prefix in ["solace_ai_connector", "."]:
                for prefix in [
                    ".components",
                    ".components.general",
                    ".components.general.for_testing",
                    ".components.general.llm.langchain",
                    ".components.general.llm.openai",
                    ".components.general.llm.litellm",
                    ".components.general.db.mongo",
                    ".components.general.websearch",
                    ".components.inputs_outputs",
                    ".transforms",
                    ".common",
                ]:
                    full_name = f"{prefix_prefix}{prefix}.{module}"
                    try:
                        if full_name.startswith("."):
                            return importlib.import_module(
                                full_name, package=__package__
                            )
                        else:
                            return importlib.import_module(full_name)
                    except ModuleNotFoundError as e:
                        name = str(e.name)
                        if (
                            name != "solace_ai_connector"
                            and name.split(".")[-1] != full_name.split(".")[-1]
                        ):
                            raise ModuleNotFoundError(
                                f"Module '{full_name}' not found"
                            ) from None
                    except Exception:
                        raise ImportError(
                            f"Module load error for {full_name}"
                        ) from None
        raise ModuleNotFoundError(f"Module '{module}' not found") from None


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
        # obj = import_module(module)

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
                # if not allow_source_expression:
                #     raise ValueError(
                #         "evaluate_expression() is not allowed in this context"
                #     )
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
        return formatted_payload.encode("utf-8")
    elif encoding == "base64":
        return base64.b64encode(formatted_payload.encode("utf-8"))
    elif encoding == "gzip":
        return gzip.compress(formatted_payload.encode("utf-8"))
    else:
        return formatted_payload


def decode_payload(payload, encoding, payload_format):
    if encoding == "base64":
        try:
            payload = base64.b64decode(payload)
        except Exception:
            log.error("Error decoding base64 payload")
            raise ValueError("Error decoding base64 payload") from None
    elif encoding == "gzip":
        try:
            payload = gzip.decompress(payload)
        except Exception:
            log.error("Error decompressing gzip payload")
            raise ValueError("Error decompressing gzip payload") from None
    elif encoding == "utf-8" and (
        isinstance(payload, bytes) or isinstance(payload, bytearray)
    ):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            log.error("Error decoding UTF-8 payload")
            raise ValueError("Error decoding UTF-8 payload") from None
    elif encoding == "unicode_escape":
        try:
            payload = payload.decode("unicode_escape")
        except UnicodeDecodeError:
            log.error("Error decoding unicode_escape payload")
            raise ValueError("Error decoding unicode_escape payload") from None

    if payload_format == "json":
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            log.error("Error decoding JSON payload")
            raise ValueError("Error decoding JSON payload") from None
    elif payload_format == "yaml":
        try:
            payload = yaml.safe_load(payload)
        except Exception:
            log.error("Error decoding YAML payload")
            raise ValueError("Error decoding YAML payload") from None

    return payload


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
            current_data = current_data[int(part)]
        # If the current data is neither a dictionary nor a list, or if 'part' is
        # not a number, return None
        elif isinstance(current_data, object):
            current_data = getattr(current_data, part, None)
        else:
            raise ValueError(
                f"Could not get data value for expression '{expression}' - data "
                "is not a dictionary or list"
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
        data_object[expression] = value
        return

    data_name = expression.split(":")[1]

    # It is an error if the data_object is None or not a dictionary or list
    if data_object is None:
        raise ValueError(
            f"Could not set data value for expression '{expression}' - data_object is None"
        ) from None
    if not isinstance(data_object, dict) and not isinstance(data_object, list):
        raise ValueError(
            f"Could not set data value for expression '{expression}' - data_object "
            "is not a dictionary or list"
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
        # If we're at the last part of the path, set the value
        if i == len(path_parts) - 1:
            if isinstance(current_data, dict):
                current_data[part] = value
            elif isinstance(current_data, list) and part.isdigit():
                while len(current_data) <= int(part):
                    current_data.append(None)
                current_data[int(part)] = value
            else:
                log.error(
                    "Could not set data value for expression '%s' - "
                    "data is not a dictionary or list",
                    expression,
                )
        # If we're not at the last part of the path, move to the next part
        else:
            next_part_is_digit = path_parts[i + 1].isdigit()
            if isinstance(current_data, dict):
                current_data = current_data.setdefault(
                    part, [] if next_part_is_digit else {}
                )
            elif isinstance(current_data, list) and part.isdigit():
                while len(current_data) <= int(part):
                    current_data.append(None)
                if current_data[int(part)] is None:
                    current_data[int(part)] = [] if next_part_is_digit else {}
                current_data = current_data[int(part)]
            else:
                log.error(
                    "Could not set data value for expression '%s' - data "
                    "is not a dictionary or list",
                    expression,
                )
                return


def remove_data_value(data_object, expression):
    if ":" not in expression:
        data_object.pop(expression, None)
        return

    data_name = expression.split(":")[1]

    # It is an error if the data_object is None or not a dictionary or list
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

    # Split the data_name by dots to get the path
    path_parts = data_name.split(".")

    # Start with the entire data_object
    current_data = data_object

    # Traverse the path
    for i, part in enumerate(path_parts):
        # If we're at the last part of the path, remove the value
        if i == len(path_parts) - 1:
            if isinstance(current_data, dict):
                current_data.pop(part, None)
            elif isinstance(current_data, list) and part.isdigit():
                if len(current_data) > int(part):
                    current_data.pop(int(part))
            else:
                log.error(
                    "Could not remove data value for expression '%s' - "
                    "data is not a dictionary or list",
                    expression,
                )
        # If we're not at the last part of the path, move to the next part
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
                return


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
            # If key doesn't exist: add it
            result[k] = v
    return result
