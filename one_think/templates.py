"""
Prompt Templates System for AI-ONE.

Loads and renders prompt templates from templates/ directory using Jinja2.
Supports variable substitution and template logic for customizable prompts.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, Template


class PromptTemplateLoader:
    """
    Loads and renders prompt templates using Jinja2.
    
    Templates are stored in templates/ directory and can contain variables
    that are substituted at runtime using {{ variable }} syntax.
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize template loader.
        
        Args:
            templates_dir: Path to templates directory (default: templates/)
        """
        if templates_dir is None:
            # Default to templates/ in project root
            project_root = Path(__file__).parent.parent
            templates_dir = project_root / "templates"
        
        self.templates_dir = Path(templates_dir)
        
        # Initialize Jinja2 environment
        if self.templates_dir.exists():
            loader = FileSystemLoader(str(self.templates_dir))
            self.env = Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)
        else:
            self.env = None
    
    def load_template(self, template_name: str, **variables) -> str:
        """
        Load and render a template with variables.
        
        Args:
            template_name: Name of template file (e.g., 'system_prompt.txt')
            **variables: Variables to substitute in template
            
        Returns:
            Rendered template string
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If templates directory not found
        """
        if self.env is None:
            raise ValueError(f"Templates directory not found: {self.templates_dir}")
        
        try:
            template = self.env.get_template(template_name)
            return template.render(**variables)
        except Exception as e:
            raise FileNotFoundError(f"Template '{template_name}' not found or invalid: {e}")
    
    def get_system_prompt(self, available_tools: str = "") -> str:
        """
        Get the main system prompt with tool information.
        
        Args:
            available_tools: Comma-separated list of available tools
            
        Returns:
            Rendered system prompt
        """
        try:
            return self.load_template('system_prompt.txt', available_tools=available_tools)
        except (FileNotFoundError, ValueError):
            # Fallback to hardcoded prompt if template not available
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
        
        Args:
            base_prompt: Base system prompt
            reason: Reason for refresh
            message_count: Number of messages in session
            tool_count: Number of tool calls made
            tools_summary: Summary of available tools
            
        Returns:
            Rendered refresh prompt
        """
        try:
            return self.load_template(
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

=== CONTEXT REFRESH ===
Refresh reason: {reason}
Session stats: {message_count} messages, {tool_count} tool calls
{tools_summary}

Continue the conversation with refreshed context and guidelines."""
    
    def _get_fallback_system_prompt(self, available_tools: str) -> str:
        """Fallback system prompt when template not available."""
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


# Global template loader instance
template_loader = PromptTemplateLoader()