"""
AI-ONE - Advanced AI Assistant with Tool Integration

Modern AI assistant built on GitHub Copilot CLI with structured conversation
management, comprehensive tool ecosystem, and clean provider abstraction.

Architecture:
- Core: Session management, protocol parsing, execution engine
- Providers: LLM provider integrations (Copilot CLI, OpenAI, etc.)  
- Tools: Extensible tool ecosystem for AI capabilities

Usage:
    # Modern interface (recommended)
    python main.py

    # Legacy simple interface
    python main.py --legacy
"""

# Core imports for external use
from one_think.core.session import Session
from one_think.core.executor import Executor
from one_think.core.protocol import Protocol
from one_think.providers import create_provider, CopilotProvider
from one_think.copilot_wrapper import CopilotWrapper

# Tool imports
from one_think.tools.ai_web_search_tool import AIWebSearchTool
from one_think.tools.credentials_tool import CredentialsTool
from one_think.tools.dux_search_tool import DuxSearchTool
from one_think.tools.google_workspace_tool import GoogleWorkspaceTool
from one_think.tools.memory_tool import MemoryTool
from one_think.tools.messenger_tool import MessengerTool
from one_think.tools.python_executor_tool import PythonExecutorTool
from one_think.tools.soul_tool import SoulTool
from one_think.tools.user_tool import UserTool
from one_think.tools.web_fetch import WebFetch
from one_think.tools.whisper_tool import WhisperTool
from one_think.tools.write_to_file import WriteToFile

VERSION = "1.0.0"

# Legacy function for backward compatibility
def run():
    """
    DEPRECATED: Legacy simple conversation loop.
    
    This function is kept for backward compatibility only.
    Use CopilotWrapper or main_modern.py for new implementations.
    """
    import warnings
    warnings.warn(
        "run() is deprecated. Use CopilotWrapper or main_modern.py instead.", 
        DeprecationWarning, 
        stacklevel=2
    )
    
    # Simple fallback using new architecture
    from one_think.copilot_wrapper import CopilotWrapper
    
    print("🚀 AI-ONE Legacy Interface")
    print("Note: This is a compatibility mode. Use 'python main.py' for full features.")
    print("=" * 60)
    
    wrapper = CopilotWrapper()
    
    while True:
        try:
            prompt = input("\nEnter your prompt: ").strip()
            if not prompt:
                continue
                
            if prompt.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
                
            session_id, response = wrapper.ask_question(prompt)
            print(f"\n🤖 Response: {response}")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


__all__ = [
    # Core components
    'Session',
    'Executor', 
    'Protocol',
    'CopilotWrapper',
    'create_provider',
    'CopilotProvider',
    
    # Tools
    'AIWebSearchTool',
    'CredentialsTool', 
    'DuxSearchTool',
    'GoogleWorkspaceTool',
    'MemoryTool',
    'MessengerTool', 
    'PythonExecutorTool',
    'SoulTool',
    'UserTool',
    'WebFetch',
    'WhisperTool',
    'WriteToFile',
    
    # Legacy
    'run',
    'VERSION'
]
