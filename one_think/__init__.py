"""
AI-ONE

Modern AI assistant with structured conversation
management, tool integration, and provider abstraction.

This package provides:
- Modern architecture with Executor + Provider + Session + Tools
- Backward-compatible simple interface via run()
- Rich conversation management via AiOneWrapper

Usage:
    # Simple backward-compatible interface
    from one_think import run
    run()
    
    # Modern wrapper interface  
    from one_think import AiOneWrapper, ask_question
    wrapper = AiOneWrapper()
    session_id, response = wrapper.ask_question("Hello")
    
    # Or use the convenience function
    session_id, response = ask_question("Hello")
"""

from .aione_wrapper import (
    AiOneWrapper,
    AiOneConfig, 
    ask_question,
    get_aione_wrapper,
    configure_aione,
    get_aione_stats
)

# Legacy simple interface (using modern wrapper internally)
def run():
    """
    Run the simple conversation loop (backward compatibility).
    
    This is the original simple interface, now powered by
    the modern architecture internally.
    """
    print("🚀 AI-ONE Simple Interface")
    print("Type 'quit', 'exit', or 'q' to exit")
    print("-" * 40)
    
    session_id = None
    
    try:
        while True:
            user_input = input("👤 You: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            try:
                print("🤖 AI: ", end="", flush=True)
                session_id, response = ask_question(user_input, session_id)
                print(response)
                print()
            except KeyboardInterrupt:
                print("\n⏸️  Request interrupted")
                continue
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
                
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


# Export main components
__all__ = [
    'run',
    'AiOneWrapper',
    'AiOneConfig',
    'ask_question', 
    'get_aione_wrapper',
    'configure_aione',
    'get_aione_stats'
]
