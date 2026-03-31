from one_think.tools import Tool
from typing import Any, Dict, Tuple
from pathlib import Path


class WriteToFile(Tool):
    """
    Tool for writing content to a file.
    """

    name: str = "write_to_file"
    description: str = "Writes content to a file at a given path."

    DEFAULT_MODE = "w"

    def execute(self, arguments: Dict[str, Any] | None = None) -> Tuple[str, str]:
        arguments = arguments or {}

        if arguments.get("help"):
            return self.get_full_information(), ""

        path_str = arguments.get("path")
        if not path_str or not isinstance(path_str, str):
            return "", "Missing or invalid argument: 'path'"

        content = arguments.get("content", "")
        if not isinstance(content, str):
            content = str(content)

        mode = arguments.get("mode", self.DEFAULT_MODE)

        if not isinstance(mode, str):
            return "", "'mode' must be a string"

        mode = mode.strip().lower()

        if mode not in {"w", "a"}:
            return "", "Invalid mode. Use 'w' (overwrite) or 'a' (append)"

        path = Path(path_str)

        try:
            if path.exists() and path.is_dir():
                return "", "Path points to a directory, not a file"

            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open(mode, encoding="utf-8") as f:
                f.write(content)

            return f"Successfully wrote to {path.resolve()}", ""

        except PermissionError:
            return "", "Permission denied"
        except OSError as e:
            return "", f"File system error: {e}"
        except Exception as e:
            return "", f"Unexpected error: {e}"

    def get_full_information(self) -> str:
        return (
            f"Tool: {self.name}\n"
            "Description: Writes content to a file.\n\n"
            "Usage:\n"
            "- path (str, required): target file path\n"
            "- content (str, optional): text to write (default='')\n"
            f"- mode (str, optional): 'w' (overwrite) or 'a' (append), default='{self.DEFAULT_MODE}'\n"
            "- help (bool, optional): show this message\n\n"
            "Behavior:\n"
            "- Creates parent directories if they do not exist\n"
            "- Overwrites or appends depending on mode\n"
            "- Returns absolute path on success\n"
        )


if __name__ == "__main__":
    tool = WriteToFile()

    result, error = tool.execute({
        "path": "output.txt",
        "content": "Hello from WriteToFile tool!",
        "mode": "w"
    })

    if error:
        print(f"Error: {error}")
    else:
        print(result)