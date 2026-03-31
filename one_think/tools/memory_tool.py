from one_think.tools import Tool
import os
from dotenv import load_dotenv

load_dotenv()


class MemoryTool(Tool):
    name = "memory"
    description = "Manages the MEMORY.md file - important information and context the model should remember. Operations: read, write, append, clear, help."
    arguments = {
        "help": "bool (if true, returns detailed information about the tool)",
        "operation": "string (operation to perform: 'read', 'write', 'append', 'clear', 'help')",
        "content": "string (content to write or append, required for 'write' and 'append' operations)"
    }
    
    def __init__(self):
        super().__init__()
        self.memory_path = self._get_memory_path()
    
    def _get_memory_path(self) -> str:
        """Get MEMORY.md file path from .env or use default."""
        memory_path = os.getenv("MEMORY_PATH")
        
        if not memory_path:
            # Default to MEMORY.md in persistent directory
            memory_path = "persistent/MEMORY.md"
        
        return memory_path
    
    def _ensure_file_exists(self):
        """Ensure MEMORY.md file exists, create if not."""
        if not os.path.exists(self.memory_path):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.memory_path) or '.', exist_ok=True)
            
            # Create file with default template
            default_content = """# MEMORY - Important Context

This file stores important information that the model should remember across sessions.

"""
            try:
                with open(self.memory_path, 'w', encoding='utf-8') as f:
                    f.write(default_content)
            except Exception as e:
                raise Exception(f"Cannot create MEMORY.md file: {e}")
    
    def _read_memory(self):
        """Read content from MEMORY.md file."""
        try:
            self._ensure_file_exists()
            
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                return "MEMORY.md file is empty", ""
            
            return content, ""
        except Exception as e:
            return "", f"Error reading MEMORY.md: {e}"
    
    def _write_memory(self, content: str):
        """Write content to MEMORY.md file (overwrite)."""
        try:
            if not content:
                return "", "Content cannot be empty for 'write' operation"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.memory_path) or '.', exist_ok=True)
            
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            lines_count = len(content.split('\n'))
            chars_count = len(content)
            
            return f"Successfully wrote to MEMORY.md ({lines_count} lines, {chars_count} characters)", ""
        except Exception as e:
            return "", f"Error writing to MEMORY.md: {e}"
    
    def _append_memory(self, content: str):
        """Append content to MEMORY.md file."""
        try:
            if not content:
                return "", "Content cannot be empty for 'append' operation"
            
            self._ensure_file_exists()
            
            with open(self.memory_path, 'a', encoding='utf-8') as f:
                # Add newline if file doesn't end with one
                f.write('\n' + content if not content.startswith('\n') else content)
            
            return f"Successfully appended to MEMORY.md ({len(content)} characters)", ""
        except Exception as e:
            return "", f"Error appending to MEMORY.md: {e}"
    
    def _clear_memory(self):
        """Clear MEMORY.md file content."""
        try:
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                f.write("")
            
            return "Successfully cleared MEMORY.md", ""
        except Exception as e:
            return "", f"Error clearing MEMORY.md: {e}"
    
    def _show_help(self):
        """Show help information for the Memory tool."""
        help_text = """Memory Tool - MEMORY.md Management

DESCRIPTION:
    Manages the MEMORY.md file containing important context and information
    that the model should remember across sessions.
    File path is configured in .env via MEMORY_PATH (default: persistent/MEMORY.md).

OPERATIONS:
    read    - Read and display the entire content of MEMORY.md
    write   - Write new content to MEMORY.md (overwrites existing content)
    append  - Append content to the end of MEMORY.md
    clear   - Clear all content from MEMORY.md
    help    - Show this help message

ARGUMENTS:
    help (optional)      - If true, show this help message
    operation (required) - The operation to perform
    content (optional)   - Content for write/append operations

EXAMPLES:
    1. Read memory:
       {"operation": "read"}
    
    2. Write new memory:
       {"operation": "write", "content": "# Important context..."}
    
    3. Append to memory:
       {"operation": "append", "content": "\\n## New info\\n- Remember X"}
    
    4. Clear memory:
       {"operation": "clear"}
    
    5. Show help:
       {"operation": "help"}
       OR
       {"help": true}

MEMORY.MD PURPOSE:
    - Store important context across sessions
    - Remember key decisions and their rationale
    - Track learned user preferences
    - Document important facts about the project
    - Keep notes on recurring issues or patterns
    - Store information that should persist

WHAT TO STORE:
    ✅ Important project decisions
    ✅ User preferences discovered during conversations
    ✅ Key facts about the codebase or architecture
    ✅ Lessons learned from past mistakes
    ✅ Recurring patterns or issues
    ✅ Important context that shouldn't be forgotten
    ✅ Custom workflows or procedures
    
    ❌ Sensitive personal data
    ❌ Passwords or credentials (use credentials_tool)
    ❌ Temporary notes (use regular files)

USAGE PATTERNS:

    1. After important decisions:
       Store the decision and reasoning for future reference
    
    2. When user corrects you:
       Remember the correction to avoid repeating mistakes
    
    3. Learning preferences:
       Track user's style preferences, naming conventions, etc.
    
    4. Project context:
       Remember key aspects of the project that are frequently relevant

CONFIGURATION:
    Set MEMORY_PATH in .env file:
        MEMORY_PATH=persistent/MEMORY.md

NOTES:
    - File is automatically created with default template if it doesn't exist
    - Use 'write' to completely replace content
    - Use 'append' to add to existing content
    - MEMORY.md is stored in persistent/ (not committed to git)
    - Review and clean periodically to keep relevant
"""
        return help_text, ""
    
    def execute(self, arguments: dict[str, str] = None):
        """Execute the MEMORY operation."""
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
            return self._read_memory()
        
        elif operation == "write":
            content = arguments.get("content")
            if content is None:
                return "", "Missing required argument for 'write': content"
            return self._write_memory(content)
        
        elif operation == "append":
            content = arguments.get("content")
            if content is None:
                return "", "Missing required argument for 'append': content"
            return self._append_memory(content)
        
        elif operation == "clear":
            return self._clear_memory()
        
        elif operation == "help":
            return self._show_help()
        
        else:
            return "", f"Unknown operation: '{operation}'. Valid operations: read, write, append, clear, help"


if __name__ == "__main__":
    # Test the tool
    tool = MemoryTool()
    
    print("=" * 60)
    print("Testing Memory Tool")
    print("=" * 60)
    
    # Test 1: Show help
    print("\n1. Showing help...")
    result, error = tool.execute({
        "operation": "help"
    })
    if error:
        print(f"Error: {error}")
    else:
        print(result[:300] + "...")
    
    # Test 2: Read (will create default if not exists)
    print("\n2. Reading MEMORY.md...")
    result, error = tool.execute({
        "operation": "read"
    })
    if error:
        print(f"Error: {error}")
    else:
        print(f"Content preview (first 200 chars):\n{result[:200]}...")
    
    # Test 3: Append important info
    print("\n3. Appending important information...")
    important_info = """
## Session 2026-03-31

### Important Decisions
- Created memory system to track important context
- Memory stored in persistent/MEMORY.md

### Learned Preferences
- User prefers concise responses
- Keep documentation minimal
"""
    result, error = tool.execute({
        "operation": "append",
        "content": important_info
    })
    if error:
        print(f"Error: {error}")
    else:
        print(f"Result: {result}")
    
    # Test 4: Read updated content
    print("\n4. Reading updated MEMORY.md...")
    result, error = tool.execute({
        "operation": "read"
    })
    if error:
        print(f"Error: {error}")
    else:
        print(f"Total length: {len(result)} characters")
        print(f"Lines: {len(result.split(chr(10)))}")
    
    print("\n" + "=" * 60)
    print("Testing completed!")
    print("=" * 60)
