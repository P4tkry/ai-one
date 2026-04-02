# Prompt Instructions README

This directory contains Jinja2 instruction files for AI-ONE system prompts and messages.

## Instruction Files

### `system_prompt.txt`
Main system prompt instruction with variable substitution:
- `{{ available_tools }}`: Comma-separated list of available tools
- Used for initial system prompt and as base for refresh scenarios

### `refresh_prompt.txt`
Instruction for system refresh prompts with context:
- `{{ base_prompt }}`: Original system prompt
- `{{ reason }}`: Reason for refresh
- `{{ message_count }}`: Number of messages in session
- `{{ tool_count }}`: Number of tool calls made
- `{{ tools_summary }}`: Summary of available tools

**When is refresh prompt used?**
- **Context overload**: Too many messages in conversation
- **Format errors**: LLM stops responding in proper JSON format
- **Tool changes**: Tools added/removed during session
- **System reset**: Need to "restart" system prompt while keeping session context

It's like rebooting the AI's instructions without losing conversation history.

## Usage

Instructions are automatically loaded by the `PromptInstructionLoader` class:

```python
from one_think.templates import instruction_loader

# Load system prompt with tools
prompt = instruction_loader.get_system_prompt(available_tools="memory, web_fetch")

# Load refresh prompt with context
refresh = instruction_loader.get_refresh_prompt(
    base_prompt="Base prompt...",
    reason="context full",
    message_count=25,
    tool_count=8,
    tools_summary="Available tools: memory, web_fetch"
)
```

## Instruction Syntax

Uses Jinja2 syntax for variable substitution:
- `{{ variable }}`: Simple variable substitution
- Instructions support all Jinja2 features: loops, conditionals, filters, etc.

## Fallbacks

If instruction files are not found, the system falls back to hardcoded prompts to ensure reliability.

## Editing Instructions

You can edit these files directly to customize AI-ONE's behavior:
1. Modify prompt content, instructions, or formatting
2. Add new variables (update the code to pass them)
3. Use Jinja2 features for dynamic content generation

Changes take effect immediately - no restart required.