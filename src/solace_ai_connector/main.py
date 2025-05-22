import os
import sys
import re
import yaml
import signal
import argparse
from dotenv import load_dotenv

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
        config = yaml.safe_load(yaml_str)

        # If there are flows but no apps, create an app with the filename as the name
        if config and "flows" in config and not config.get("apps"):
            app_name = os.path.splitext(os.path.basename(file))[0]
            config["apps"] = [{"name": app_name, "flows": config["flows"]}]
            del config["flows"]

        return config

    except Exception:  # pylint: disable=locally-disabled, broad-exception-caught
        print("Error loading configuration file")
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
            raise FileNotFoundError("Included file not found.") from None
        included_content = process_includes(full_path, os.path.dirname(full_path))
        # Indent each line of the included content
        indented_content = "\n".join(
            indent + line for line in included_content.splitlines()
        )
        return indented_content

    # Updated regex to handle !include correctly
    include_pattern = re.compile(
        r'^([ \t]*)!include\s+(["\']?[^"\s\']+)["\']?', re.MULTILINE
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
                # For other lists, we want to concatenate them
                merged[key] = dict1[key] + dict2[key]
            else:
                # For other types, we want to use the second value
                merged[key] = dict2[key]
        elif key in dict1:
            merged[key] = dict1[key]
        else:
            merged[key] = dict2[key]
    return merged


def main():
    parser = argparse.ArgumentParser(
        description="Solace AI Event Connector: Connect Solace brokers to AI/ML models and services."
    )
    parser.add_argument(
        "--envfile",
        metavar="<file>",
        type=str,
        help="Load environment variables from a specified .env file.",
    )
    parser.add_argument(
        "config_files",
        metavar="<config.yaml>",
        type=str,
        nargs="+",  # Require at least one config file
        help="One or more YAML configuration files for the connector.",
    )

    args = parser.parse_args()

    # Load .env file if specified
    if args.envfile:
        if os.path.exists(args.envfile):
            load_dotenv(dotenv_path=args.envfile, override=True)
            print(f"Loaded environment variables from {args.envfile}")
        else:
            print(
                f"Warning: Specified --envfile '{args.envfile}' not found.",
                file=sys.stderr,
            )

    # Use the config files provided via arguments
    files = args.config_files

    # Loop over the configuration files
    full_config = {}
    for file in files:
        if not os.path.exists(file):
            print(f"Error: Configuration file '{file}' not found.", file=sys.stderr)
            sys.exit(1)
        # Load the configuration from the file
        config = load_config(file)
        # Merge the configuration into the full configuration
        full_config = merge_config(full_config, config)

    # Create the connector instance
    sac = SolaceAiConnector(full_config, config_filenames=files)

    def shutdown():
        """Shutdown the connector."""
        print("Stopping Solace AI Connector")
        sac.stop()
        sac.cleanup()
        print("Solace AI Connector exited successfully!")
        sys.exit(0)

    def signal_handler(signum, frame):
        if signum == signal.SIGINT:
            raise KeyboardInterrupt("CTRL+C pressed") from None
        elif signum == signal.SIGTERM:
            raise SystemExit("SIGTERM received") from None

    if sys.platform == "win32":
        import win32api

        def handler(type):
            # Map Windows signals to Python exceptions for consistent handling
            if type == signal.CTRL_C_EVENT:
                print("\nCTRL+C pressed, initiating shutdown...")
                # Raising KeyboardInterrupt here might not work reliably across threads
                # Directly call shutdown for Windows console events
                shutdown()
                return True  # Indicate we handled it
            elif type == signal.CTRL_BREAK_EVENT:
                print("\nCTRL+BREAK pressed, initiating shutdown...")
                shutdown()
                return True
            # Add other Windows signals if needed (CTRL_CLOSE_EVENT, etc.)
            return False  # Let default handler run for other signals

        win32api.SetConsoleCtrlHandler(handler, True)
    else:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    # Start the connector
    try:
        sac.run()
        sac.wait_for_flows()
        # If wait_for_flows completes without interruption, initiate clean shutdown
        shutdown()
    except (KeyboardInterrupt, SystemExit) as e:
        print(f"Shutdown initiated due to {type(e).__name__}.")
        shutdown()
    except Exception as e:
        print(f"Error running Solace AI Connector: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        # Attempt graceful shutdown even on unexpected errors
        try:
            shutdown()
        except Exception as shutdown_err:
            print(f"Error during shutdown: {shutdown_err}", file=sys.stderr)
            sys.exit(1)  # Exit with error code if shutdown fails


if __name__ == "__main__":
    main()
