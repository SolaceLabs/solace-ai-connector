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
                            import_path = line[
                                len("from solace_ai_event_connector.") :
                            ].strip()
                            the_rest = import_path.split(" ", 1)[1]
                            import_path = import_path.split(" ")[0]
                            file_relative_path = os.path.relpath(dirpath, root_dir)

                            import_parts = import_path.split(".")
                            file_parts = file_relative_path.split(os.sep)
                            depth = len(file_parts)
                            if depth == 1 and file_parts[0] == ".":
                                depth = 0
                            while True:
                                if (
                                    len(file_parts)
                                    and len(import_parts)
                                    and import_parts[0] == file_parts[0]
                                ):
                                    import_parts.pop(0)
                                    file_parts.pop(0)
                                    depth -= 1
                                else:
                                    break

                            relative_import = "." * (depth + 1) + ".".join(import_parts)

                            file.write(f"from {relative_import} {the_rest}\n")
                        else:
                            file.write(line)


if __name__ == "__main__":
    # Change directory to src
    os.chdir("src")
    root_directory = "solace_ai_event_connector"
    convert_imports(root_directory)
