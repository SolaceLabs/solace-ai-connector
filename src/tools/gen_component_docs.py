import os
import re
import sys
import json
import glob
import importlib.util
import yaml  # pylint: disable=import-error

sys.path.append("src")


# Function to descend into a directory and find all Python files
def find_python_files(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            # Skip if 'for_testing' is in the path
            if "for_testing" in root:
                continue
            if file.endswith(".py"):
                yield os.path.join(root, file)


# For each Python file, import it and see if it has a info dictionary at the top level
def find_info_dicts(directory):
    for file in find_python_files(directory):
        # Dynamically import the module
        if file.endswith("__init__.py"):
            continue
        if "/solace_ai_connector/" in file:
            module_name = re.sub(
                r".*/solace_ai_connector/",
                "solace_ai_connector/",
                file,
            )
            module_name = module_name.replace("/", ".")
            if module_name.endswith(".py"):
                module_name = module_name[:-3]

        spec = importlib.util.spec_from_file_location(module_name, file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Check if the module has an info dictionary
        if hasattr(module, "info"):
            yield file, module.info


# For each info dictionary, create the markdown documentation
current_component = ""
full_info = {}


def create_markdown_documentation(directory, output_dir, module_type):
    components = []

    # full_info contains all the info dictionaries. This will be used later
    # to produce an AI prompt to help users create a new configuration
    full_info[module_type] = []
    for file, info in find_info_dicts(directory):
        # Get the base file name without the extension
        name = re.sub(r".*/", "", file)
        name = re.sub(r".py$", "", name)
        global current_component  # pylint: disable=global-statement
        current_component = name

        full_info[module_type].append(info)

        # Create the markdown documentation
        markdown = f"# {info['class_name']}\n\n"
        markdown += f"{info['description']}\n\n"
        markdown += "## Configuration Parameters\n\n"
        markdown += "```yaml\n"
        if module_type == "component":
            markdown += "component_name: <user-supplied-name>\n"
            markdown += f"component_module: {name}\n"
            markdown += "component_config:\n"
        elif module_type == "transform":
            markdown += "input_transforms:\n"
            markdown += f"  type: {name}\n"
        for param in info["config_parameters"]:
            markdown += f"  {param['name']}: <{param.get('type', 'string')}>\n"
        markdown += "```\n\n"

        if "config_parameters" in info and len(info["config_parameters"]) > 0:
            markdown += "| Parameter | Required | Default | Description |\n"
            markdown += "| --- | --- | --- | --- |\n"
            for param in info["config_parameters"]:
                markdown += f"| {param['name']} | {param.get('required', False)} | {param.get('default', '')} | {param['description']} |\n"
            markdown += "\n"
        else:
            markdown += "No configuration parameters\n\n"

        if "request_schema" in info:
            print(f"{name} has a request schema")
        if "input_schema" in info:
            fields = []
            markdown += "\n## Component Input Schema\n\n```\n"
            markdown += format_json_schema(info["input_schema"], fields)
            markdown += "\n```\n"
            # markdown += "\n## Component Input Schema Fields\n\n"
            markdown += format_fields(fields)

        if "output_schema" in info:
            fields = []
            markdown += "\n\n## Component Output Schema\n\n```\n"
            markdown += format_json_schema(info["output_schema"], fields)
            markdown += "\n```\n"
            # markdown += "\n## Component Output Schema Fields\n\n"
            markdown += format_fields(fields)

        if "example_config" in info:
            markdown += "\n\n## Example Configuration\n\n"
            markdown += info["example_config"]

        # Write all the files into "./docs" and change the .py to .md
        # The files are uniquely named without the path, so we can remove that
        file = re.sub(r".*/", "", file)
        file = re.sub(r".py$", ".md", file)
        components.append(
            {
                "file": file,
                "name": re.sub(r"\..*", "", file),
                "description": info.get(
                    "short_description", info.get("description", "")
                ),
            }
        )
        file = f"{output_dir}/{file}"

        # Write the markdown to a file
        with open(file, "w", encoding="utf-8") as f:
            f.write(markdown)

    markdown = ""

    # Create the component index table

    # Capitalize the type
    type_title = module_type.capitalize() if isinstance(module_type, str) else ""
    markdown += f"# Built-in {type_title}s\n\n"

    markdown += "| Component | Description |\n"
    markdown += "| --- | --- |\n"

    # Sort the components by name
    components = sorted(components, key=lambda x: x["name"])

    for component in components:
        markdown += f"| [{component['name']}]({component['file']}) | {component['description']} |\n"

    with open(f"{output_dir}/index.md", "w", encoding="utf-8") as f:
        f.write(markdown)


def create_ai_prompt(info):
    """Use the info dictionary to create an AI prompt to help users create a
    new configuration. This prompt will contain all the component and transform information,
    information about the purpose of the connector and an example configuration. Later, the
    user will have to provide the message {input_schema, queue, topic}, and the desired
    output_schema and topic.

    """

    system_prompt = (
        "You are an assistant who will help users create a new configuration for the "
        "Solace AI Event Connector. The connector is a tool that allows users to create "
        "flows that process messages from a Solace event broker, generally to help interface "
        "with AI based services. A typical flow will start with a message from the broker, "
        "pass through a series of components and transforms, and then send the message back to "
        "the broker. The components and transforms are user-configurable and can be used to "
        "manipulate the message in various ways. The user will have to provide the message "
        "input_schema, queue, or topic, and the desired output_schema and topic. Your job is to "
        "to create an initial configuration for the user. \n"
        "Make sure you use ${ENV_VARS} for any sensitive information. \n"
        "Your interaction with the user will via a chat interface. Before you generate the "
        "YAML configuration, you will have to ask the user for the input_schema, queue, or topic, "
        "and the desired output_schema and topic. \n"
        "You can ask as many questions as you need to get the information you need. Try to make "
        "the conversation flow naturally and confirm the user's input if there is any ambiguity - "
        "for example, if they input the schema in a mixed JSON/YAML/pseudo structure, print it "
        "back out for them in a clean YAML format and get confirmation that it is correct\n"
    )

    # Read in docs/configuration.md
    with open("docs/configuration.md", "r", encoding="utf-8") as f:
        configuration_prompt = f.read()

    # Read in an example configuration
    # with open("examples/milvus_store.yaml", "r", encoding="utf-8") as f:
    #     example_config = f.read()

    prompt = (
        "Here is a structure that defines all the built-in components and transforms. \n"
        f"<transform_and_components_yaml>\n{yaml.dump(info, default_flow_style=False)}\n"
        "</transform_and_components_yaml>\n\n"
        "Here is the markdown documentation for the configuration file: \n"
        f"<markdown_documentation>\n{configuration_prompt}\n</markdown_documentation>\n"
        "Here is an example configuration: \n"
        "Take special care to ensure that the data format is correct as it moves component to "
        "component. input_transforms will likely need to be created to ensure that the data is "
        "in the correct format for each component. \n"
        "Now, you will have to ask the user for the input_schema, queue, or topic, and the desired "
        "output_schema and topic. \n"
    )

    # Write out a prompts.yaml file
    prompts = {
        "system_prompt": system_prompt,
        "prompt": prompt,
    }
    with open("prompts.yaml", "w", encoding="utf-8") as f:
        f.write(yaml.dump(prompts, default_style=">", default_flow_style=True))

    print(prompts["system_prompt"])
    print(prompts["prompt"])

    with open("prompts.txt", "w", encoding="utf-8") as f:
        f.write(prompts["system_prompt"])
        f.write(prompts["prompt"])


def format_json_schema(
    schema_dict, field_list, level=0, first_line_string="", prop_path=""
):
    indent = "  " * level
    output = ""
    if schema_dict is None:
        print(f"Schema is None for {current_component}")
        return ""
    if "type" not in schema_dict:
        print(f"Missing type in schema: {schema_dict} for {current_component}")
        return ""
    if schema_dict["type"] == "object":
        # output += f"{indent}{{{first_line_string}\n"
        output += f"{indent}{{{first_line_string}\n"
        required = schema_dict.get("required", [])
        for prop_name, prop_data in schema_dict.get("properties", {}).items():
            field_list.append(
                {
                    "name": prop_path + "." + prop_name if prop_path else prop_name,
                    "required": prop_name in required,
                    "description": prop_data.get("description", ""),
                    "data": prop_data,
                }
            )
            output += f"{indent}  {prop_name}: "
            output += format_json_schema(
                prop_data,
                field_list,
                level + 1,
                "",
                prop_path + f"{prop_name}",
            )
            # If not the last property, add a comma
            if prop_name != list(schema_dict["properties"].keys())[-1]:
                output += ","
            output += "\n"
        # If there were no properties, add <freeform-object> to indicate that any object is allowed
        if not schema_dict.get("properties"):
            output += f"{indent}  <freeform-object>\n"
        output += f"{indent}}}"
    elif schema_dict["type"] == "array":
        # output += f"{indent}[{first_line_string}\n"
        output += f"[{first_line_string}\n"
        output += format_json_schema(
            schema_dict.get("items"), field_list, level + 1, "", prop_path + "[]"
        )
        output += f",\n{indent}  ...\n"
        output += f"{indent}]"
    else:
        output += f"{indent}<{schema_dict['type']}>"

    return output


def format_fields(fields):
    if not fields or len(fields) == 0:
        return ""
    # Put the fields in a markdown table
    output = "| Field | Required | Description |\n"
    output += "| --- | --- | --- |\n"
    for field in fields:
        output += (
            f"| {field['name']} | {field['required']} | {field['description']} |\n"
        )
    return output


def format_response_schema_for_markdown(response_schema):
    """
    Converts a response schema dictionary into a Markdown-formatted string.

    Args:
        response_schema (dict): The response schema dictionary.

    Returns:
        str: A Markdown-formatted string representing the schema.
    """

    def recursive_markdown(data, level=0):
        """Recursively builds the Markdown."""
        lines = []
        indent = "  " * level

        if data["type"] == "object":
            lines.append(f"{indent}" "{")
            for prop_name, prop_data in data.get("properties", {}).items():
                if prop_data.get("type", "invalid") == "object":
                    lines.append(f"{indent}  {prop_name}:")
                    lines.extend(recursive_markdown(prop_data, level + 2))
                lines.append(f"{indent}  {prop_name}:")
                lines.extend(recursive_markdown(prop_data, level + 2))
            lines.append(f"{indent}" "}")

        elif data["type"] == "array":
            lines.append(f"{indent}* **Array of:**")
            lines.extend(recursive_markdown(data.get("items"), level + 1))

        else:  # Base type
            lines.append(f"{indent}* **{data['type']}**")

        if "required" in data:
            lines.append(f"{indent}_(Required fields: {', '.join(data['required'])})_")

        return lines

    # Start the Markdown output
    output = "```json\n"
    output += json.dumps(response_schema, indent=2)  # Pretty-print JSON
    output += "\n```\n\n"

    # Add formatted description using the recursive helper
    output += "**Detailed Schema Description**\n\n"
    output += "\n".join(recursive_markdown(response_schema))

    return output


# Example schema:
# "output_schema": {
#     "type": "object",
#     "properties": {
#         "results": {
#             "type": "object",
#             "properties": {
#                 "matches": {
#                     "type": "array",
#                     "items": {
#                         "type": "object",
#                         "properties": {
#                             "text": {"type": "string"},
#                             "metadata": {"type": "object"},
#                             "score": {"type": "float"},
#                         },
#                         "required": ["text"],
#                     },
#                 },
#             },
#         }
#     },
#     "required": ["results"],
# },


def schema_as_human_readable_string(schema):
    if schema["type"] == "object":
        return schema_as_human_readable_string(schema["properties"])
    elif schema["type"] == "array":
        return schema_as_human_readable_string(schema["items"])
    else:
        return schema["type"]


def print_usage():
    # Get the basename of the script (remove dirs)
    name = os.path.basename(sys.argv[0])
    print(f"Usage: {name} [base_directory]")


def main():
    # Get a base directory from the command line
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    elif not os.path.exists("src/solace_ai_connector"):
        if glob.glob("src/*/components"):
            base_dir = "."
        else:
            print("You must specify a base directory for the components\n")
            print_usage()
            sys.exit(1)
    else:
        base_dir = "src/solace_ai_connector"

    # Call the function
    create_markdown_documentation(
        f"{base_dir}/components", "docs/components", "component"
    )
    create_markdown_documentation(
        f"{base_dir}/transforms", "docs/transforms", "transform"
    )

    # create_ai_prompt(full_info)


if __name__ == "__main__":
    main()
