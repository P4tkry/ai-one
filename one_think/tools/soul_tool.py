from one_think.tools import Tool
import os
from dotenv import load_dotenv

load_dotenv()


class SoulTool(Tool):
    name = "soul"
    description = "Manages the SOUL.md file - system instructions and behavior guidelines."

    
    def __init__(self):
        super().__init__()
        self.soul_path = self._get_soul_path()
    
    def _get_soul_path(self) -> str:
        """Get SOUL.md file path from .env or use default."""
        soul_path = os.getenv("SOUL_PATH")
        
        if not soul_path:
            # Default to SOUL.md in persistent directory
            soul_path = "persistent/SOUL.md"
        
        return soul_path
    
    def _ensure_file_exists(self):
        """Ensure SOUL.md file exists, create if not."""
        if not os.path.exists(self.soul_path):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.soul_path) or '.', exist_ok=True)
            
            # Create file with default template
            default_content = """# SOUL - System Instructions

## System Behavior

This section defines how the system should behave and operate.

"""
            try:
                with open(self.soul_path, 'w', encoding='utf-8') as f:
                    f.write(default_content)
            except Exception as e:
                raise Exception(f"Cannot create SOUL.md file: {e}")
    
    def _read_soul(self):
        """Read content from SOUL.md file."""
        try:
            self._ensure_file_exists()
            
            with open(self.soul_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                return "SOUL.md file is empty", ""
            
            return content, ""
        except Exception as e:
            return "", f"Error reading SOUL.md: {e}"
    
    def _write_soul(self, content: str):
        """Write content to SOUL.md file (overwrite)."""
        try:
            if not content:
                return "", "Content cannot be empty for 'write' operation"
            
            with open(self.soul_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            lines_count = len(content.split('\n'))
            chars_count = len(content)
            
            return f"Successfully wrote to SOUL.md ({lines_count} lines, {chars_count} characters)", ""
        except Exception as e:
            return "", f"Error writing to SOUL.md: {e}"
    
    def _append_soul(self, content: str):
        """Append content to SOUL.md file."""
        try:
            if not content:
                return "", "Content cannot be empty for 'append' operation"
            
            self._ensure_file_exists()
            
            with open(self.soul_path, 'a', encoding='utf-8') as f:
                # Add newline if file doesn't end with one
                f.write('\n' + content if not content.startswith('\n') else content)
            
            return f"Successfully appended to SOUL.md ({len(content)} characters)", ""
        except Exception as e:
            return "", f"Error appending to SOUL.md: {e}"
    
    def _clear_soul(self):
        """Clear SOUL.md file content."""
        try:
            with open(self.soul_path, 'w', encoding='utf-8') as f:
                f.write("")
            
            return "Successfully cleared SOUL.md", ""
        except Exception as e:
            return "", f"Error clearing SOUL.md: {e}"
    
    def _show_help(self):
        """Show help information for the Soul tool."""
        help_text = """Soul Tool - SOUL.md Management

DESCRIPTION:
    Manages the SOUL.md file containing system instructions and behavior guidelines.
    File path is configured in .env via SOUL_PATH (default: SOUL.md).

OPERATIONS:
    read    - Read and display the entire content of SOUL.md
    write   - Write new content to SOUL.md (overwrites existing content)
    append  - Append content to the end of SOUL.md
    clear   - Clear all content from SOUL.md
    help    - Show this help message

ARGUMENTS:
    operation (required) - The operation to perform
    content (optional)   - Content for write/append operations

EXAMPLES:
    1. Read current instructions:
       {"operation": "read"}
    
    2. Write new instructions:
       {"operation": "write", "content": "# New SOUL instructions..."}
    
    3. Append additional guidelines:
       {"operation": "append", "content": "\\n## New Section\\n- Rule 1"}
    
    4. Clear all instructions:
       {"operation": "clear"}
    
    5. Show help:
       {"operation": "help"}

SOUL.MD PURPOSE:
    - Define system behavior and personality
    - Set communication style and tone
    - Establish operating principles
    - Configure technical preferences
    - Specify response format
    - Define error handling approach

CONFIGURATION:
    Set SOUL_PATH in .env file:
        SOUL_PATH=SOUL.md

NOTES:
    - File is automatically created with default template if it doesn't exist
    - Use 'write' to completely replace content
    - Use 'append' to add to existing content
    - SOUL.md can be committed to repository (contains instructions, not secrets)
"""
        return help_text, ""
    
    def execute(self, arguments: dict[str, str] = None):
        """Execute the SOUL operation."""
        if arguments is None:
            return "", "No arguments provided"
        
        # Check for help first
        if arguments.get("help"):
            return self._show_help()
        
        operation = arguments.get("operation")
        if not operation:
            return "", "Missing required argument: 'operation'"
        
        # Execute operation
        if operation == "read":
            return self._read_soul()
        
        elif operation == "write":
            content = arguments.get("content")
            if content is None:
                return "", "Missing required argument for 'write': content"
            return self._write_soul(content)
        
        elif operation == "append":
            content = arguments.get("content")
            if content is None:
                return "", "Missing required argument for 'append': content"
            return self._append_soul(content)
        
        elif operation == "clear":
            return self._clear_soul()
        
        elif operation == "help":
            return self._show_help()
        
        else:
            return "", f"Unknown operation: '{operation}'. Valid operations: read, write, append, clear, help"


if __name__ == "__main__":
    # Test the tool
    tool = SoulTool()
    
    print("=" * 60)
    print("Testing Soul Tool")
    print("=" * 60)
    
    # Test 1: Show help
    print("\n1. Showing help...")
    result, error = tool.execute({
        "operation": "help"
    })
    if error:
        print(f"Error: {error}")
    else:
        print(result)
    
    # Test 2: Read
    print("\n2. Reading SOUL.md...")
    result, error = tool.execute({
        "operation": "read"
    })
    if error:
        print(f"Error: {error}")
    else:
        print(f"Content preview (first 200 chars):\n{result[:200]}...")
    
    print("\n" + "=" * 60)
    print("Testing completed!")
    print("=" * 60)
