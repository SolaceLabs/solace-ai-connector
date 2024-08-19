"""Random utility functions"""

import importlib.util
import os
import sys
import re
import builtins
import subprocess

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


def import_module(name, base_path=None, component_package=None):
    """Import a module by name"""

    if component_package:
        install_package(component_package)

    if base_path:
        if base_path not in sys.path:
            sys.path.append(base_path)
    try:
        module = importlib.import_module(name)
        return module
    except ModuleNotFoundError as exc:
        # If the module does not have a path associated with it, try
        # importing it from the known prefixes - annoying that this
        # is necessary. It seems you can't dynamically import a module
        # that is listed in an __init__.py file :(
        if "." not in name:
            for prefix_prefix in ["solace_ai_connector", "."]:
                for prefix in [
                    ".components",
                    ".components.general",
                    ".components.general.for_testing",
                    ".components.general.langchain",
                    ".components.inputs_outputs",
                    ".transforms",
                    ".common",
                ]:
                    full_name = f"{prefix_prefix}{prefix}.{name}"
                    try:
                        if full_name.startswith("."):
                            module = importlib.import_module(
                                full_name, package=__package__
                            )
                        else:
                            module = importlib.import_module(full_name)
                        return module
                    except ModuleNotFoundError:
                        pass
                    except Exception as e:
                        raise ImportError(
                            f"Module load error for {full_name}: {e}"
                        ) from e
        raise ModuleNotFoundError(f"Module '{name}' not found") from exc


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
        raise ValueError("Cannot have both module and object in an 'invoke' config")

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
                (expression, data_type) = extract_source_expression(value)
                positional[index] = create_lambda_function_for_source_expression(
                    expression, data_type=data_type
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
                (expression, data_type) = extract_source_expression(value)
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


def extract_source_expression(se_call):
    # First remove the source_expression( and the trailing )
    # Account for possible whitespace
    expression = se_call.split("source_expression(")[1].split(")")[0].strip()
    data_type = None
    if "," in expression:
        (expression, data_type) = re.split(r"\s*,\s*", expression)

    if not expression:
        raise ValueError("source_expression() must contain an expression")
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
