"""
Prompt Instructions System for AI-ONE.

Loads and renders prompt instructions from prompt_instructions/ directory using Jinja2.
Supports variable substitution and template logic for customizable prompts.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template


class PromptInstructionLoader:
    """
    Loads and renders prompt instructions using Jinja2.
    
    Instructions are stored in prompt_instructions/ directory and can contain variables
    that are substituted at runtime using {{ variable }} syntax.
    """
    
    def __init__(self, instructions_dir: Optional[str] = None):
        """
        Initialize instruction loader.
        
        Args:
            instructions_dir: Path to instructions directory (default: one_think/prompt_instructions/)
        """
        if instructions_dir is None:
            # Default to prompt_instructions/ in one_think package
            package_root = Path(__file__).parent
            instructions_dir = package_root / "prompt_instructions"
        
        self.instructions_dir = Path(instructions_dir)
        
        # Initialize Jinja2 environment
        if self.instructions_dir.exists():
            loader = FileSystemLoader(str(self.instructions_dir))
            self.env = Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
        else:
            self.env = None
    
    def load_instruction(self, instruction_name: str, **variables) -> str:
        """
        Load and render an instruction with variables.
        
        Args:
            instruction_name: Name of instruction file (e.g., 'system_prompt.txt')
            **variables: Variables to substitute in instruction
            
        Returns:
            Rendered instruction string
            
        Raises:
            FileNotFoundError: If instruction file doesn't exist
            ValueError: If instructions directory not found
        """
        if self.env is None:
            raise ValueError(f"Instructions directory not found: {self.instructions_dir}")
        
        try:
            template = self.env.get_template(instruction_name)
            return template.render(**variables)
        except Exception as e:
            raise FileNotFoundError(f"Instruction '{instruction_name}' not found or invalid: {e}")
    
    def get_system_prompt(self, tool_registry=None) -> str:
        """
        Get the main system prompt with tool information.
        
        Args:
            tool_registry: Optional tool registry for detailed tool info
            
        Returns:
            Rendered system prompt
        """
        try:
            # Generate formatted tools list
            if tool_registry:
                available_tools = tool_registry.get_tools_formatted("detailed")
            else:
                available_tools = ""
                
            return self.load_instruction('system_prompt.txt', available_tools=available_tools)
        except (FileNotFoundError, ValueError):
            # Fallback to hardcoded prompt if instruction not available
            return self._get_fallback_system_prompt(available_tools)
    
    def get_refresh_prompt(
        self, 
        base_prompt: str, 
        reason: str, 
        message_count: int, 
        tool_count: int, 
        tools_summary: str
    ) -> str:
        """
        Get the system refresh prompt with context.
        
        REFRESH PROMPT is used when:
        - Context becomes too long (message_count high)
        - LLM stops following JSON format 
        - Tools change during session
        - System needs to "reset" while preserving session context
        
        It's like restarting the system prompt but with current session state.
        
        Args:
            base_prompt: Base system prompt
            reason: Reason for refresh (e.g., "context full", "format error")
            message_count: Number of messages in session
            tool_count: Number of tool calls made
            tools_summary: Summary of available tools
            
        Returns:
            Rendered refresh prompt
        """
        try:
            return self.load_instruction(
                'refresh_prompt.txt',
                base_prompt=base_prompt,
                reason=reason,
                message_count=message_count,
                tool_count=tool_count,
                tools_summary=tools_summary
            )
        except (FileNotFoundError, ValueError):
            # Fallback to simple concatenation
            return f"""{base_prompt}

=== SYSTEM REFRESH ===
Refresh reason: {reason}
Session context: {message_count} messages, {tool_count} tool calls
{tools_summary}

IMPORTANT: Return to strict JSON format and follow all original guidelines."""
    
    def _get_fallback_system_prompt(self, available_tools: str) -> str:
        """Fallback system prompt when instruction not available."""
        return f"""You are an advanced AI assistant powered by AI-ONE tool system.

CRITICAL: Always respond with valid JSON in one of these formats:

1. For normal responses:
{{"type": "response", "content": "your helpful answer here"}}

2. For tool requests:
{{"type": "tool_request", "tools": [{{"tool_name": "tool_name", "params": {{}}, "id": "req_1"}}]}}

3. For system refresh:
{{"type": "system_refresh_request", "reason": "context full or need guidelines"}}

Available tools: {available_tools}

Use tools when you need to gather information, execute code, or perform actions.
Always provide helpful, accurate responses in the specified JSON format."""


# Global instruction loader instance
instruction_loader = PromptInstructionLoader()