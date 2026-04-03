# Prompt Instructions README

This directory contains Jinja2 instruction files for AI-ONE system prompts and messages.

## Architecture

The system prompt uses a highly modular 5-part architecture for maximum maintainability and clarity:

### 5-Part Modular System
- **`01_identity.txt`** - Role definition, primary objective, override principles
- **`02_behaviour.txt`** - Operational style, persistence policy, ambition level, quality threshold
- **`03_execution_policy.txt`** - Problem decomposition, retry strategy, failure conditions, plan/act/verify loop
- **`04_tools_policy.txt`** - Tool help requirements, chaining policy, workflow orchestration, error handling
- **`05_io_contract.txt`** - Strict JSON output, response types, malformed recovery, file input protocol

### Runtime Components
- **`runtime_prompt.txt`** - Persistent runtime directive added to every request
- **`refresh_prompt.txt`** - System refresh prompt template

## Loading Logic

1. **System Prompt**: Load 5-part modular components (01-05) and combine them (sent once per session)
2. **Runtime Prompt**: Load and add to every single request (persistent reminder)
3. **Fallback**: Use hardcoded prompt if files not available

## Component Details

### `01_identity.txt` (1,067 chars)
Core identity and purpose:
- Role definition as sophisticated AI agent
- Primary objective of task completion
- Override principles that prioritize quality over convenience

### `02_behaviour.txt` (1,419 chars)  
Operational behavior patterns:
- Methodical problem-solving style
- High persistence through challenges
- High ambition level for complex solutions
- Strict quality standards

### `03_execution_policy.txt` (1,753 chars)
Task execution methodology:
- Systematic problem decomposition approach
- Progressive retry strategy with fallbacks
- Clear failure condition definitions
- Plan → Act → Verify → Iterate loop

### `04_tools_policy.txt` (1,976 chars)
Tool usage and workflow orchestration:
- Mandatory tool help requirement before first use
- Advanced tool chaining and parallel execution
- Comprehensive workflow orchestration capabilities
- Robust error handling for tool failures

### `05_io_contract.txt` (2,543 chars)
Input/output format contracts:
- Strict JSON output requirements
- Complete response type definitions
- JSON validation and error recovery procedures  
- File input protocol specification

### `runtime_prompt.txt` (1,166 chars)
Persistent runtime directive added to every request:
- Core task completion reminder
- Key operational rules (JSON output, tool usage, etc.)
- Context recovery mechanism for uncertain situations
- Final reminders for consistent behavior

This is different from the main system prompt (sent once per session) - runtime prompt is included in every single request to ensure consistent behavior.

### `refresh_prompt.txt`
System refresh template with context variables:
- `{{ base_prompt }}`: Original system prompt
- `{{ reason }}`: Reason for refresh
- `{{ message_count }}`: Number of messages in session
- `{{ tool_count }}`: Number of tool calls made
- `{{ tools_summary }}`: Summary of available tools

## Benefits of 5-Part Architecture

✅ **Maximum Modularity**: Each file has a single, clear responsibility
✅ **Precise Editing**: Modify specific behaviors without affecting others
✅ **Clear Separation**: Identity, behavior, execution, tools, and I/O are distinct
✅ **Easy Maintenance**: Small, focused files are easier to understand and modify
✅ **Systematic Organization**: Logical flow from identity → behavior → execution → tools → I/O

## Usage

Instructions are automatically loaded by the `PromptInstructionLoader` class:

```python
from one_think.templates import PromptInstructionLoader

loader = PromptInstructionLoader()

# Load complete 5-part system prompt (sent once per session)
system_prompt = loader.get_system_prompt(tool_registry)

# Load runtime prompt (added to every request)
runtime_prompt = loader.get_runtime_prompt()

# Load specific component
identity = loader.load_instruction('01_identity.txt')
behaviour = loader.load_instruction('02_behaviour.txt')
# ... etc

# Load refresh prompt with context
refresh = loader.get_refresh_prompt(
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

## Editing Instructions

You can edit these files directly to customize AI-ONE's behavior:
1. **Identity**: Modify core role and objectives
2. **Behavior**: Adjust operational style and standards
3. **Execution**: Change problem-solving methodology
4. **Tools**: Update tool usage and workflow policies
5. **I/O Contract**: Modify output formats and protocols

Changes take effect immediately - no restart required.