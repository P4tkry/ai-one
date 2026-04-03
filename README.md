# AI-ONE

> Modern conversational AI system with structured tool integration and multi-provider architecture.

## Overview

AI-ONE is a sophisticated conversational AI framework that provides:

- **Multi-Provider Architecture**: Support for various LLM backends (Copilot CLI, OpenAI, Anthropic)
- **Structured Tool Integration**: Extensible tool ecosystem with JSON-based communication
- **Session Management**: Persistent conversation state and context handling  
- **Debug Visibility**: Comprehensive logging for development and troubleshooting
- **Modern Design**: Clean 3-layer architecture with clear separation of concerns

## Quick Start

```bash
# Clone and setup
git clone <your-repo-url> ai-one
cd ai-one
pip install -r requirements.txt

# Run with default settings
python main.py

# Or use modern interface directly
python modern_main.py --help
```

## Architecture

```
ai-one/
├── main.py                    # Primary entry point
├── modern_main.py             # Modern CLI interface  
└── one_think/
    ├── __init__.py            # Package exports (AiOneWrapper, etc.)
    ├── aione_wrapper.py       # Main user interface class
    ├── debug.py               # Debug logging system
    ├── core/                  # Execution engine, sessions, protocol
    │   ├── executor.py        # Conversation execution engine
    │   ├── session.py         # Session state management
    │   ├── protocol.py        # JSON message protocol parsing
    │   └── config.py          # Configuration management
    ├── providers/             # LLM backend integrations
    │   ├── copilot/           # GitHub Copilot CLI provider
    │   ├── openai/            # OpenAI API provider
    │   └── base.py            # Provider interface
    └── tools/                 # Tool ecosystem
        ├── registry.py        # Tool discovery and management
        ├── web_fetch.py       # Web content fetching
        ├── python_executor.py # Python code execution
        └── ...                # Additional tools
```

## Usage

### Basic Usage

```python
from one_think import ask_question

# Simple question
session_id, response = ask_question("What is the weather like?")
print(response)

# Continue conversation
session_id, response = ask_question("What about tomorrow?", session_id=session_id)
```

### Advanced Usage

```python
from one_think import AiOneWrapper, AiOneConfig

# Custom configuration
config = AiOneConfig(
    model="gpt-4.1",
    max_tool_iterations=10,
    system_prompt="You are a helpful AI assistant specialized in..."
)

# Create wrapper instance
wrapper = AiOneWrapper(config)

# Ask questions with full control
session = wrapper.get_or_create_session()
response = wrapper.ask_question("Complex question requiring tools", session_id=session.session_id)
```

## JSON Protocol

AI-ONE uses a structured JSON communication protocol:

### Message Types

#### 1. System Messages
```json
{
  "author": "system",
  "message": "You are an advanced AI assistant powered by AI-ONE..."
}
```

#### 2. User Messages  
```json
{
  "author": "user", 
  "message": "What is the capital of France?"
}
```

#### 3. Tool Messages
```json
{
  "author": "tool",
  "message": "Tool execution result: Paris is the capital of France"
}
```

### Response Types

#### 1. Normal Response
```json
{
  "type": "response",
  "content": "The capital of France is Paris."
}
```

#### 2. Tool Request
```json
{
  "type": "tool_request",
  "tools": [
    {
      "tool_name": "web_search",
      "params": {"query": "capital of France"},
      "id": "req_1"
    }
  ]
}
```

#### 3. System Refresh Request
```json
{
  "type": "system_refresh_request",
  "reason": "context full or need updated guidelines"
}
```

## Available Tools

AI-ONE comes with a comprehensive tool ecosystem:

| Tool | Description |
|------|-------------|
| `web_fetch` | Fetch and process web content |
| `python_executor` | Execute Python code safely |
| `memory` | Persistent memory storage |
| `user` | Interactive user input |
| `whisper` | Audio transcription |
| `google_workspace` | Google Workspace integration |
| `messenger` | Communication tools |
| `credentials` | Secure credential management |

### Adding Custom Tools

```python
from one_think.tools.base import BaseTool
from pydantic import BaseModel

class MyCustomTool(BaseTool):
    name = "my_custom_tool"
    description = "Does something amazing"
    
    class Input(BaseModel):
        parameter: str
        
    class Output(BaseModel):
        result: str
    
    def execute(self, input: Input) -> Output:
        # Your tool logic here
        return Output(result=f"Processed: {input.parameter}")
```

## Debug Mode

Enable comprehensive debug logging:

```bash
# Windows PowerShell
$env:DEBUG = "1"
python main.py

# Linux/Mac
export DEBUG=1
python main.py
```

Debug output includes:
- 🔍 Component lifecycle tracking
- 📊 Request/response timing  
- 🛠️ Tool execution details
- 🧠 LLM call/response logging
- 📝 Session state changes
- ⚡ Performance metrics

## Configuration

### Environment Variables

```bash
DEBUG=1                    # Enable debug logging
MODEL=gpt-4.1             # Default LLM model
MAX_ITERATIONS=5          # Max tool execution loops
PROVIDER=copilot          # Default provider
```

### Config File

```python
config = AiOneConfig(
    model="gpt-4.1",
    provider="copilot",
    max_tool_iterations=5,
    system_prompt="Custom system prompt...",
    tools_enabled=True,
    debug_mode=False
)
```

## Providers

### GitHub Copilot CLI Provider (Default)

```bash
# Requires GitHub Copilot CLI installed
pip install github-copilot-cli
copilot auth login
```

### OpenAI Provider

```python
config = AiOneConfig(
    provider="openai",
    model="gpt-4",
    api_key="your-openai-api-key"  # Or set OPENAI_API_KEY env var
)
```

### Custom Provider

```python
from one_think.providers.base import BaseProvider

class MyCustomProvider(BaseProvider):
    def send_messages(self, messages, model=None):
        # Implementation for your LLM backend
        pass
```

## Special Tool Configurations

### TTS (Text-to-Speech) Tool

The TTS tool uses **Microsoft Edge TTS** (edge-tts) which provides high-quality, multilingual speech synthesis with 300+ voices in 100+ languages.

#### Installation and Setup

```bash
# TTS is automatically available with AI-ONE installation
pip install edge-tts  # Already included in requirements.txt
```

#### TTS Tool Features

- **🎯 Voice Listing**: Browse 300+ Microsoft voices with filtering by language/gender
- **🗣️ Text Synthesis**: Convert text to speech with natural-sounding voices  
- **🌍 Multilingual Support**: Support for 100+ languages and locales
- **📊 Voice Information**: Get detailed metadata about specific voices
- **🎵 High Quality Audio**: 24kHz WAV output with excellent clarity
- **🚀 No API Keys**: Uses Microsoft Edge Speech Services (no authentication required)

#### Usage Examples

```python
# List English voices
response = wrapper.ask_question("""
Use the tts tool to list English (US) voices, limit to 5 results.
""")

# Synthesize speech
response = wrapper.ask_question("""
Use the tts tool to synthesize: "Hello! This is AI-ONE with Edge TTS." 
Use voice en-US-AriaNeural and save to outputs/hello.wav
""")

# Multilingual synthesis
response = wrapper.ask_question("""
Use tts tool to synthesize Polish text: "Witaj świecie! To jest test TTS."
Use Polish voice pl-PL-MarekNeural.
""")
```

#### Available Operations

- **`list_voices`** - Browse available voices with filtering
- **`synthesize`** - Generate speech from text  
- **`get_voice_info`** - Get detailed voice metadata

#### Popular Voices

- **English**: `en-US-AriaNeural` (Female), `en-US-GuyNeural` (Male)
- **Polish**: `pl-PL-MarekNeural` (Male), `pl-PL-ZofiaNeural` (Female)
- **French**: `fr-FR-DeniseNeural` (Female), `fr-FR-HenriNeural` (Male)
- **German**: `de-DE-KatjaNeural` (Female), `de-DE-ConradNeural` (Male)
- **Spanish**: `es-ES-ElviraNeural` (Female), `es-ES-AlvaroNeural` (Male)

#### Technical Details

- **Output Format**: 24kHz 16-bit mono WAV
- **Network**: Requires internet connection for synthesis
- **Performance**: ~500-1000ms synthesis time depending on text length
- **Compatibility**: Works with all Python versions (3.8+)
- **Storage**: Audio files saved to `outputs/` directory by default

## Development

### Running Tests

```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests  
python -m pytest tests/integration/

# All tests with coverage
python -m pytest --cov=one_think tests/
```

### Code Quality

```bash
# Linting
pylint one_think/

# Formatting
black one_think/

# Type checking
mypy one_think/
```

## Docker Deployment

```bash
# Build and run
docker-compose up --build

# Development mode with live reload
docker-compose -f docker-compose.dev.yml up
```

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes with tests
4. Run quality checks: `pylint`, `black`, `pytest`
5. Submit pull request

## License

[Your License Here]

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](issues/)
- 💬 [Discussions](discussions/)
- 📧 Email: [your-email]

---

**AI-ONE** - Modern conversational AI with structured tool integration