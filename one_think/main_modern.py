"""
Modern main entry point for AI-ONE using new architecture.

This provides both the new rich conversation interface and
backward compatibility with the original simple loop.
"""

import sys
import argparse
from typing import Optional

from one_think.copilot_wrapper import CopilotWrapper, CopilotConfig
from one_think import run as legacy_run  # Original implementation


def run_modern_copilot(config: Optional[CopilotConfig] = None):
    """
    Run the modern Copilot interface with full AI-ONE architecture.
    
    Features:
    - Session-based conversations
    - Tool integration via Tool Registry
    - Provider abstraction for LLM backends
    - Rich usage statistics and monitoring
    """
    wrapper = CopilotWrapper(config)
    
    print("🚀 AI-ONE Modern Interface")
    print("="*50)
    print(f"Model: {wrapper.config.model}")
    print(f"Tools: {'Enabled' if wrapper.config.enable_tools else 'Disabled'}")
    
    if wrapper.config.enable_tools:
        stats = wrapper.get_usage_stats()
        tool_count = stats['executor'].get('tool_count', 0)
        print(f"Available tools: {tool_count}")
    
    print("\nType 'quit', 'exit', or 'q' to exit")
    print("Type '/stats' to see usage statistics")
    print("Type '/sessions' to list active sessions")
    print("Type '/help' for more commands")
    print("-"*50)
    
    session_id = None
    
    while True:
        try:
            # Get user input
            prompt = input("\n👤 You: ").strip()
            
            if not prompt:
                continue
            
            # Handle special commands
            if prompt.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
                
            elif prompt == '/stats':
                stats = wrapper.get_usage_stats()
                print("\n📊 Usage Statistics:")
                print(f"  Provider requests: {stats['provider']['requests']}")
                print(f"  Tokens sent: {stats['provider']['tokens_sent']}")
                print(f"  Tokens received: {stats['provider']['tokens_received']}")
                print(f"  Total time: {stats['provider']['total_time_ms']:.1f}ms")
                print(f"  Active sessions: {stats['sessions']['active_count']}")
                print(f"  Total messages: {stats['sessions']['total_messages']}")
                continue
                
            elif prompt == '/sessions':
                sessions = wrapper.list_sessions()
                print(f"\n📋 Active Sessions ({len(sessions)}):")
                for session in sessions:
                    print(f"  {session['session_id']}: {session['message_count']} messages")
                continue
                
            elif prompt == '/clear':
                if session_id:
                    wrapper.clear_session(session_id)
                    session_id = None
                    print("🧹 Session cleared. Starting fresh.")
                else:
                    print("ℹ️  No active session to clear.")
                continue
                
            elif prompt == '/help':
                print("\n🆘 Available Commands:")
                print("  /stats    - Show usage statistics")
                print("  /sessions - List active sessions")
                print("  /clear    - Clear current session")
                print("  /help     - Show this help")
                print("  quit/exit/q - Exit the program")
                continue
            
            # Process the prompt
            print("🤖 Copilot: ", end="", flush=True)
            
            try:
                session_id, response = wrapper.ask_question(
                    prompt, 
                    session_id=session_id
                )
                print(response)
                
            except KeyboardInterrupt:
                print("\n⚠️  Request interrupted by user.")
                continue
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                continue
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except EOFError:
            print("\n👋 Goodbye!")
            break


def run_legacy_interface():
    """Run the original AI-ONE interface for backward compatibility."""
    print("🔄 Running legacy AI-ONE interface...")
    print("(Use --modern flag for the new interface)")
    print()
    legacy_run()


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="AI-ONE - Advanced AI Assistant with Tool Integration"
    )
    
    parser.add_argument(
        "--modern", 
        action="store_true",
        help="Use the modern Copilot interface (default)"
    )
    
    parser.add_argument(
        "--legacy", 
        action="store_true",
        help="Use the legacy interface"
    )
    
    parser.add_argument(
        "--model", 
        default="gpt-4.1",
        help="LLM model to use (default: gpt-4.1)"
    )
    
    parser.add_argument(
        "--no-tools", 
        action="store_true",
        help="Disable tool integration"
    )
    
    parser.add_argument(
        "--max-iterations", 
        type=int, 
        default=5,
        help="Maximum tool iterations per request (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Determine which interface to use
    use_modern = not args.legacy  # Default to modern unless --legacy specified
    
    if use_modern:
        # Create configuration
        config = CopilotConfig(
            model=args.model,
            enable_tools=not args.no_tools,
            max_tool_iterations=args.max_iterations
        )
        
        run_modern_copilot(config)
    else:
        run_legacy_interface()


if __name__ == "__main__":
    main()