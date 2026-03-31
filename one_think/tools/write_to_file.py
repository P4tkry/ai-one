from one_think.tools import Tool
from typing import Any, Dict, Tuple
from pathlib import Path


class WriteToFile(Tool):
    """
    Tool for writing content to a file.
    """

    name: str = "write_to_file"
    description: str = "Writes content to a file at a given path."

    arguments: Dict[str, str] = {
        "help": "bool (if true, returns detailed information about the tool)",
        "path": "str (path to the file)",
        "content": "str (content to write)",
        "mode": "str (file mode: 'w' = overwrite, 'a' = append)"
    }

    def execute(self, arguments: Dict[str, Any] | None = None) -> Tuple[str, str]:
        arguments = arguments or {}

        if arguments.get("help"):
            return self.get_full_information(), ""

        path_str: str | None = arguments.get("path")
        if not path_str:
            return "", "Missing required argument: 'path'"

        content: str = str(arguments.get("content", ""))
        mode: str = arguments.get("mode", "w")

        if mode not in {"w", "a"}:
            return "", "Invalid mode. Use 'w' (write) or 'a' (append)"

        path = Path(path_str)

        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open(mode, encoding="utf-8") as f:
                f.write(content)

            return f"Successfully wrote to {path.resolve()}", ""

        except OSError as e:
            return "", f"File system error: {e}"
        except Exception as e:
            return "", f"Unexpected error: {e}"

    def get_full_information(self) -> str:
        return (
            f"Tool: {self.name}\n"
            "Description: Writes content to a file.\n\n"
            "Arguments:\n"
            "- path (str): target file path (required)\n"
            "- content (str): text to write (default='')\n"
            "- mode (str): 'w' (overwrite) or 'a' (append), default='w'\n"
            "- help (bool): show this message\n"
        )


if __name__ == "__main__":
    tool = WriteToFile()

    # Example: normal execution
    result, error = tool.execute({
        "path": "output.txt",
        "content": "Hello from WriteToFile tool!",
        "mode": "w"
    })

    if error:
        print(f"Error: {error}")
    else:
        print(result)

    # Example: help mode
    help_text, _ = tool.execute({"help": True})
    print("\n--- HELP ---")
    print(help_text)