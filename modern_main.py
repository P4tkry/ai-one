"""
AI-ONE Modern Interface - Command Line Entry Point

This script provides the modern AI-ONE command line interface with:
- Session-based conversations  
- Tool integration via Tool Registry
- Provider abstraction for LLM backends
- Rich usage statistics and monitoring

Automatically loads configuration from .env file.
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import argparse
import logging
import uuid
from typing import Optional

from one_think.aione_wrapper import AiOneWrapper, AiOneConfig

logger = logging.getLogger(__name__)


def run_modern_interface(config: Optional[AiOneConfig] = None):
    """
    Run the modern AI-ONE interface with full architecture integration.
    
    Features:
    - Session-based conversations
    - Tool integration via Tool Registry
    - Provider abstraction for LLM backends
    - Rich usage statistics and monitoring
    """
    wrapper = AiOneWrapper(config)
    
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
    
    try:
        while True:
            if session_id:
                user_input = input(f"[{session_id[:8]}...] You: ").strip()
            else:
                user_input = input("👤 You: ").strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            elif user_input == '/stats':
                stats = wrapper.get_usage_stats()
                print("\n📊 Usage Statistics:")
                print(f"  Sessions: {stats['sessions']['total_count']} active")
                print(f"  Total requests: {stats['sessions']['total_requests']}")
                if wrapper.config.enable_tools:
                    print(f"  Available tools: {stats['tools']['available_count']}")
                print()
                continue
            
            elif user_input == '/sessions':
                sessions = wrapper.list_sessions()
                if sessions:
                    print(f"\n📋 Active Sessions ({len(sessions)}):")
                    for session in sessions:
                        print(f"  {session['session_id'][:8]}... - {session['stats'].get('requests_count', 0)} requests")
                else:
                    print("\n📋 No active sessions")
                print()
                continue
            
            elif user_input == '/help':
                print("\n🔧 Available Commands:")
                print("  /stats     - Show usage statistics")
                print("  /sessions  - List active sessions")
                print("  /new       - Start new session")
                print("  /help      - Show this help")
                print("  quit/exit  - Exit the interface")
                print()
                continue
            
            elif user_input == '/new':
                session_id = None
                print("🔄 Starting new session...")
                continue
            
            # Send question to AI-ONE
            try:
                print("🤖 AI: ", end="", flush=True)
                session_id, response = wrapper.ask_question(user_input, session_id)
                print(response)
                print()
                
            except KeyboardInterrupt:
                print("\n\n⏸️  Request interrupted by user")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")
                continue
                
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")


def run_legacy_interface():
    """Run the original AI-ONE interface for backward compatibility."""
    print("🔄 Running legacy AI-ONE interface...")
    print("(Use --modern flag for the enhanced interface)")
    print()
    # Note: Legacy function available in one_think package
    from one_think import run
    run()


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="AI-ONE - Advanced AI Assistant with Tool Integration"
    )
    
    parser.add_argument(
        "--modern", 
        action="store_true",
        help="Use the modern AI-ONE interface (default)"
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
        config = AiOneConfig(
            model=args.model,
            enable_tools=not args.no_tools,
            max_tool_iterations=args.max_iterations
        )
        
        run_modern_interface(config)
    else:
        run_legacy_interface()


if __name__ == "__main__":
    main()