import os
import sys
import re
import yaml
import signal

from .solace_ai_connector import SolaceAiConnector


def load_config(file):
    """Load configuration from a YAML file."""
    try:
        # Get the directory of the current file
        file_dir = os.path.dirname(os.path.abspath(file))

        # Load the YAML file as a string, processing includes
        yaml_str = process_includes(file, file_dir)

        # Substitute the environment variables using os.environ
        yaml_str = expandvars_with_defaults(yaml_str)

        # Load the YAML string using yaml.safe_load
        return yaml.safe_load(yaml_str)

    except Exception as e:  # pylint: disable=locally-disabled, broad-exception-caught
        print(f"Error loading configuration file: {e}", file=sys.stderr)
        sys.exit(1)


def process_includes(file_path, base_dir):
    """Process #include directives in the given file."""
    with open(file_path, "r", encoding="utf8") as f:
        content = f.read()

    def include_repl(match):
        indent = match.group(1)  # Capture the leading spaces
        indent = indent.replace("\n", "")  # Remove newlines
        include_path = match.group(2).strip("'\"")
        full_path = os.path.join(base_dir, include_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Included file not found: {full_path}")
        included_content = process_includes(full_path, os.path.dirname(full_path))
        # Indent each line of the included content
        indented_content = "\n".join(
            indent + line for line in included_content.splitlines()
        )
        return indented_content

    include_pattern = re.compile(
        r'^(\s*)!include\s+(["\']?[^"\s\']+)["\']?', re.MULTILINE
    )
    return include_pattern.sub(include_repl, content)


def expandvars_with_defaults(text):
    """Expand environment variables with support for default values.
    Supported syntax: ${VAR_NAME} or ${VAR_NAME, default_value}"""
    pattern = re.compile(r"\$\{([^}:\s]+)(?:\s*,\s*([^}]*))?\}")

    def replacer(match):
        var_name = match.group(1)
        default_value = match.group(2) if match.group(2) is not None else ""
        return os.environ.get(var_name, default_value)

    return pattern.sub(replacer, text)


def merge_config(dict1, dict2):
    """Merge a new configuration into an existing configuration."""
    merged = {}
    for key in set(dict1.keys()).union(dict2.keys()):
        if key in dict1 and key in dict2:
            if isinstance(dict1[key], list) and isinstance(dict2[key], list):
                merged[key] = dict1[key] + dict2[key]
            else:
                merged[key] = dict2[key]
        elif key in dict1:
            merged[key] = dict1[key]
        else:
            merged[key] = dict2[key]
    return merged


def main():

    files = sys.argv[1:]

    if not files:
        print("No configuration files provided", file=sys.stderr)
        base_file = os.path.basename(sys.argv[0])
        print(
            f"Usage: {base_file} <config1.yaml> [<config2.yaml> ...]", file=sys.stderr
        )
        sys.exit(1)

    # Loop over the configuration files
    full_config = {}
    for file in files:
        # Load the configuration from the file
        config = load_config(file)
        # Merge the configuration into the full configuration
        full_config = merge_config(full_config, config)

    # Create the application
    app = SolaceAiConnector(full_config)

    def shutdown():
        """Shutdown the application."""
        print("Stopping Solace AI Connector")
        app.stop()
        app.cleanup()
        print("Solace AI Connector exited successfully!")
        sys.exit(0)

    signal.signal(signal.SIGINT, lambda s, f: shutdown())
    signal.signal(signal.SIGTERM, lambda s, f: shutdown())

    # Start the application
    try:
        app.run()
        app.wait_for_flows()
    except Exception as e:
        print(f"Error running Solace AI Connector: {e}", file=sys.stderr)
        shutdown()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    # Read in the configuration yaml filenames from the args
    main()
