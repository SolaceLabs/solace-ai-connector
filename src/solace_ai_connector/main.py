import os
import sys
import yaml
from .solace_ai_connector import SolaceAiConnector


def load_config(file):
    """Load configuration from a YAML file."""
    try:
        # Load the YAML file as a string
        with open(file, "r", encoding="utf8") as f:
            yaml_str = f.read()

        # Substitute the environment variables using os.environ
        yaml_str = os.path.expandvars(yaml_str)

        # Load the YAML string using yaml.safe_load
        return yaml.safe_load(yaml_str)

    except Exception as e:  # pylint: disable=locally-disabled, broad-exception-caught
        print(f"Error loading configuration file: {e}", file=sys.stderr)
        sys.exit(1)


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

    # Start the application
    app.run()

    app.wait_for_flows()

    print("Solace AI Connector exited successfully!")


if __name__ == "__main__":
    # Read in the configuration yaml filenames from the args

    main()
