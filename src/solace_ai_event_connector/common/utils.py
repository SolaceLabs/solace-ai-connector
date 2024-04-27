"""Random utility functions"""

import importlib.util
import os
import sys
import builtins

from solace_ai_event_connector.common.log import log


def import_from_directories(module_name, base_path=None):
    dirs = sys.path
    if base_path:
        dirs.append(base_path)
    for path in dirs:
        print(f"path: {path}")
        for directory in get_subdirectories(path):
            ## Skip if __pycache__ or .git
            if directory.endswith("__pycache__") or directory.endswith(".git"):
                continue
            if path == "src":
                print(f"directory: {directory}")
            module_path = os.path.join(directory, module_name + ".py")
            # print(f"module_path: {module_path}")
            if os.path.exists(module_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, module_path
                    )
                    module = importlib.util.module_from_spec(spec)
                    # Insert this module's directory into sys.path so that it
                    # can import other modules
                    sys.path.insert(0, os.path.dirname(module_path))
                    spec.loader.exec_module(module)
                except Exception as e:
                    log.error("Exception importing %s: %s", module_path, e)
                    raise e
                return module
    raise ImportError(f"Could not import module '{module_name}'")


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
    log.debug("Resolving config values in %s", config)
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
        # If the key is source_expression, we sub config to use the 'source_expression()' value in
        # invoke parameters
        config[key] = resolve_config_values(
            value,
            allow_source_expression=allow_source_expression
            or key == "source_value"
            or key == "source_expression"
            or key == "component_processing",
        )
    return config


def import_module(name, base_path=None):
    """Import a module by name"""

    if base_path:
        sys.path.append(base_path)
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError:
        try:
            module = import_from_directories(name, base_path=base_path)
        except Exception as e:
            raise ImportError(f"Module '{name}' not found ", e) from e
    return module


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
    module = config.get("module")
    obj = config.get("object")
    attribute = config.get("attribute")
    function = config.get("function")
    params = config.get("params", {})

    if module and obj:
        raise ValueError("Cannot have both module and object in an 'invoke' config")

    if module:
        obj = import_module(module)
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
                raise ValueError(f"Function '{function}' not a known python function")
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
        raise ValueError("positional must be a list")
    if keyword is not None and not isinstance(keyword, dict):
        raise ValueError("keyword must be a dict")

    # Loop through the parameters looking for source expressions and lambda functions
    have_lambda = False
    if positional:
        for index, value in enumerate(positional):
            if isinstance(value, str) and value.startswith("source_expression("):
                # if not allow_source_expression:
                #     raise ValueError(
                #         "source_expression() is not allowed in this context"
                #     )
                expression = extract_source_expression(value)
                positional[index] = create_lambda_function_for_source_expression(
                    expression
                )
                have_lambda = True
            elif callable(value):
                have_lambda = True
    if keyword:
        for key, value in keyword.items():
            if isinstance(value, str) and value.startswith("source_expression("):
                if not allow_source_expression:
                    raise ValueError(
                        "source_expression() is not allowed in this context"
                    )
                expression = extract_source_expression(value)
                keyword[key] = create_lambda_function_for_source_expression(expression)
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


def extract_source_expression(se_call):
    # First remove the source_expression( and the trailing )
    # Account for possible whitespace
    expression = se_call.split("source_expression(")[1].split(")")[0].strip()
    if not expression:
        raise ValueError("source_expression() must contain an expression")
    return expression


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


def create_lambda_function_for_source_expression(source_expression):
    """Create a lambda function that will call the source expression when invoked"""
    return lambda message: message.get_data(source_expression)


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
