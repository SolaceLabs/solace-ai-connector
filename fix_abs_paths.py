import os


def convert_imports(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                with open(file_path, "r") as file:
                    lines = file.readlines()

                with open(file_path, "w") as file:
                    for line in lines:
                        if line.startswith("from solace_ai_event_connector"):
                            # Calculate the relative import path
                            relative_path = os.path.relpath(dirpath, root_dir)
                            depth = len(relative_path.split(os.sep))
                            relative_import = (
                                "." * depth
                                + line[len("from solace_ai_event_connector") :]
                            )
                            file.write(f"from {relative_import}")
                        else:
                            file.write(line)


if __name__ == "__main__":
    root_directory = "solace_ai_event_connector"
    convert_imports(root_directory)
