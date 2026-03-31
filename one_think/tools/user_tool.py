from one_think.tools import Tool
import os
from dotenv import load_dotenv

load_dotenv()


class UserTool(Tool):
    name = "user"
    description = "Manages the USER.md file - user information and preferences. Operations: read, write, append, clear, help."
    arguments = {
        "help": "bool (if true, returns detailed information about the tool)",
        "operation": "string (operation to perform: 'read', 'write', 'append', 'clear', 'help')",
        "content": "string (content to write or append, required for 'write' and 'append' operations)"
    }
    
    def __init__(self):
        super().__init__()
        self.user_path = self._get_user_path()
    
    def _get_user_path(self) -> str:
        """Get USER.md file path from .env or use default."""
        user_path = os.getenv("USER_PATH")
        
        if not user_path:
            # Default to USER.md in persistent directory
            user_path = "persistent/USER.md"
        
        return user_path
    
    def _ensure_file_exists(self):
        """Ensure USER.md file exists, create if not."""
        if not os.path.exists(self.user_path):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.user_path) or '.', exist_ok=True)
            
            # Create file with default template
            default_content = """# USER - User Information
This file stores important information about the user, any context that should be remembered across sessions.
"""
            try:
                with open(self.user_path, 'w', encoding='utf-8') as f:
                    f.write(default_content)
            except Exception as e:
                raise Exception(f"Cannot create USER.md file: {e}")
    
    def _read_user(self):
        """Read content from USER.md file."""
        try:
            self._ensure_file_exists()
            
            with open(self.user_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                return "USER.md file is empty", ""
            
            return content, ""
        except Exception as e:
            return "", f"Error reading USER.md: {e}"
    
    def _write_user(self, content: str):
        """Write content to USER.md file (overwrite)."""
        try:
            if not content:
                return "", "Content cannot be empty for 'write' operation"
            
            with open(self.user_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            lines_count = len(content.split('\n'))
            chars_count = len(content)
            
            return f"Successfully wrote to USER.md ({lines_count} lines, {chars_count} characters)", ""
        except Exception as e:
            return "", f"Error writing to USER.md: {e}"
    
    def _append_user(self, content: str):
        """Append content to USER.md file."""
        try:
            if not content:
                return "", "Content cannot be empty for 'append' operation"
            
            self._ensure_file_exists()
            
            with open(self.user_path, 'a', encoding='utf-8') as f:
                # Add newline if file doesn't end with one
                f.write('\n' + content if not content.startswith('\n') else content)
            
            return f"Successfully appended to USER.md ({len(content)} characters)", ""
        except Exception as e:
            return "", f"Error appending to USER.md: {e}"
    
    def _clear_user(self):
        """Clear USER.md file content."""
        try:
            with open(self.user_path, 'w', encoding='utf-8') as f:
                f.write("")
            
            return "Successfully cleared USER.md", ""
        except Exception as e:
            return "", f"Error clearing USER.md: {e}"
    
    def _show_help(self):
        """Show help information for the User tool."""
        help_text = """User Tool - USER.md Management

DESCRIPTION:
    Manages the USER.md file containing user information and preferences.
    File path is configured in .env via USER_PATH (default: persistent/USER.md).

OPERATIONS:
    read    - Read and display the entire content of USER.md
    write   - Write new content to USER.md (overwrites existing content)
    append  - Append content to the end of USER.md
    clear   - Clear all content from USER.md
    help    - Show this help message

ARGUMENTS:
    operation (required) - The operation to perform
    content (optional)   - Content for write/append operations

EXAMPLES:
    1. Read user information:
       {"operation": "read"}
    
    2. Write new user information:
       {"operation": "write", "content": "# USER\\n\\n## Name\\nJohn Doe..."}
    
    3. Append additional information:
       {"operation": "append", "content": "\\n## New Project\\n- Project details"}
    
    4. Clear all information:
       {"operation": "clear"}
    
    5. Show help:
       {"operation": "help"}

USER.MD PURPOSE:
    - Store user personal information
    - Define communication preferences
    - Document technical background
    - Track current projects and goals
    - Define working style and availability

WHAT TO INCLUDE:
    - Name and role
    - Contact preferences
    - Technical skills and expertise
    - Current projects and context
    - Working hours and availability
    - Communication style preferences
    - Goals and priorities

CONFIGURATION:
    Set USER_PATH in .env file:
        USER_PATH=persistent/USER.md

NOTES:
    - File is automatically created with default template if it doesn't exist
    - Use 'write' to completely replace content
    - Use 'append' to add to existing content
    - USER.md is stored in persistent/ (not committed to git for privacy)
    - Keep sensitive personal information minimal
"""
        return help_text, ""
    
    def execute(self, arguments: dict[str, str] = None):
        """Execute the USER operation."""
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
            return self._read_user()
        
        elif operation == "write":
            content = arguments.get("content")
            if content is None:
                return "", "Missing required argument for 'write': content"
            return self._write_user(content)
        
        elif operation == "append":
            content = arguments.get("content")
            if content is None:
                return "", "Missing required argument for 'append': content"
            return self._append_user(content)
        
        elif operation == "clear":
            return self._clear_user()
        
        elif operation == "help":
            return self._show_help()
        
        else:
            return "", f"Unknown operation: '{operation}'. Valid operations: read, write, append, clear, help"


if __name__ == "__main__":
    # Test the tool
    tool = UserTool()
    
    print("=" * 60)
    print("Testing User Tool")
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
    
    # Test 2: Read (will create default if not exists)
    print("\n2. Reading USER.md...")
    result, error = tool.execute({
        "operation": "read"
    })
    if error:
        print(f"Error: {error}")
    else:
        print(f"Content preview (first 300 chars):\n{result[:300]}...")
    
    # Test 3: Write custom content
    print("\n3. Writing custom user info...")
    custom_content = """# USER - User Information

## Personal Information

- Name: John Developer
- Role: Software Engineer
- Location: Remote

## Technical Background

- Programming Languages: Python, JavaScript, Go
- Frameworks: FastAPI, React, Django
- Areas of Expertise: Backend Development, APIs, Database Design

## Current Projects

- AI-ONE: Personal AI assistant system
- Focus: Building tools for automation

## Working Style

- Preferred workflow: Agile, iterative development
- Communication: Direct and concise
- Availability: Mon-Fri, 9AM-6PM UTC
"""
    result, error = tool.execute({
        "operation": "write",
        "content": custom_content
    })
    if error:
        print(f"Error: {error}")
    else:
        print(f"Result: {result}")
    
    # Test 4: Read updated content
    print("\n4. Reading updated USER.md...")
    result, error = tool.execute({
        "operation": "read"
    })
    if error:
        print(f"Error: {error}")
    else:
        print(f"Total length: {len(result)} characters")
    
    print("\n" + "=" * 60)
    print("Testing completed!")
    print("=" * 60)
