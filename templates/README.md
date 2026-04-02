# AI-ONE Prompt Templates

This directory contains all prompt templates used by AI-ONE. You can edit these files to customize the AI's behavior and responses.

## Available Templates

### `system_prompt.txt`
Main system prompt that defines AI-ONE's behavior and JSON response format.

**Variables:**
- `{{ available_tools }}` - List of available tools

### `refresh_prompt.txt` 
System refresh prompt used when context needs to be refreshed mid-conversation.

**Variables:**
- `{{ base_prompt }}` - Base system prompt
- `{{ reason }}` - Reason for refresh
- `{{ message_count }}` - Number of messages in session
- `{{ tool_count }}` - Number of tool calls made
- `{{ tools_summary }}` - Summary of available tools

## Template Engine

Templates use **Jinja2** syntax for variables and logic:
- `{{ variable }}` - Simple variable substitution
- `{% if condition %}...{% endif %}` - Conditional blocks
- `{% for item in list %}...{% endfor %}` - Loops

## Editing Templates

1. **Edit any .txt file** in this directory
2. **Use Jinja2 syntax** for dynamic content
3. **Save the file** - changes take effect immediately
4. **Test with debug mode** to see rendered prompts

## Example Customizations

### Change AI Personality
Edit `system_prompt.txt`:
```
You are a friendly and helpful AI assistant specialized in {{ domain }}.
Always be enthusiastic and use emojis! 🚀
```

### Add Custom Instructions
Edit `system_prompt.txt`:
```
{{ base_prompt }}

ADDITIONAL RULES:
- Always ask for clarification if ambiguous
- Provide step-by-step explanations
- Include relevant examples
```

### Customize Refresh Behavior
Edit `refresh_prompt.txt`:
```
{{ base_prompt }}

=== MEMORY REFRESH ===
Previous conversation summary: {{ reason }}
Your memory has been refreshed. Continue helping the user.
```