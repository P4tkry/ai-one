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
import os
from typing import Optional

from rich.console import Console
from rich.status import Status
from rich.text import Text

from one_think.aione_wrapper import AiOneWrapper, AiOneConfig

logger = logging.getLogger(__name__)


class GitStyleStatusDisplay:
    """
    Git-style status display with sequential steps and workflow pipes.
    
    Features:
    - Sequential step completion (no parallel display)
    - Animated spinners that complete with checkmarks ✅
    - Git-style pipe visualization for workflow tools
    - Clean, professional appearance
    """
    
    def __init__(self, console: Console):
        self.console = console
        self.current_status = None
        self.current_message = ""  # Store current message for completion
        self.current_step_type = "default"
        self.workflow_active = False
        self.workflow_ending = False
        self.steps_completed = []
        
    def add_step(self, message: str, step_type: str = "default"):
        """Add new step with proper timing and workflow pipes."""
        # Complete previous step first
        if self.current_status:
            self.current_status.stop()
            
            # Show completion with appropriate prefix
            if self.workflow_active and self.current_step_type == "tool":
                if self.workflow_ending:
                    prefix = "└ "
                else:
                    prefix = "├ "
            elif self.workflow_active and self.current_step_type == "workflow":
                prefix = "├ "
            else:
                prefix = ""
                
            # Show completed step using stored message
            completed_text = Text()
            completed_text.append(prefix + self.current_message + " ✅", style="green")
            self.console.print(completed_text)
            
        # Store message for completion
        self.current_message = message
        self.current_step_type = step_type
            
        # Start new step with spinner
        if self.workflow_active and step_type == "tool":
            if self.workflow_ending:
                display_message = f"└ {message}"
            else:
                display_message = f"├ {message}"
        elif self.workflow_active and step_type == "workflow":
            display_message = f"├ {message}"
        else:
            display_message = message
            
        self.current_status = self.console.status(display_message, spinner="dots")
        self.current_status.start()
        
    def start_workflow(self):
        """Start workflow mode with git-style pipes."""
        self.workflow_active = True
        self.workflow_ending = False
        
    def end_workflow(self):
        """End workflow mode."""
        self.workflow_ending = True
        
    def complete_final(self):
        """Complete the final step."""
        if self.current_status:
            self.current_status.stop()
            
            # Show final completion
            if self.workflow_active and self.current_step_type == "tool":
                prefix = "└ " if self.workflow_ending else "├ "
            elif self.workflow_active and self.current_step_type == "workflow":
                prefix = "├ "
            else:
                prefix = ""
            completed_text = Text()
            completed_text.append(prefix + self.current_message + " ✅", style="green")
            self.console.print(completed_text)
            self.current_status = None
            self.current_message = ""
            self.current_step_type = "default"
            if self.workflow_ending:
                self.workflow_active = False
                self.workflow_ending = False
            
    def cleanup(self):
        """Clean up any running status."""
        if self.current_status:
            self.current_status.stop()
            self.current_status = None


def run_modern_interface(config: Optional[AiOneConfig] = None):
    """
    Run the modern AI-ONE interface with full architecture integration.
    
    Features:
    - Session-based conversations
    - Tool integration via Tool Registry
    - Provider abstraction for LLM backends
    - Rich usage statistics and monitoring
    - Git-style status display with visual indicators
    """
    # Set UI mode to suppress debug output
    os.environ["AI_ONE_UI_MODE"] = "true"
    
    wrapper = AiOneWrapper(config)
    console = Console()
    
    # Beautiful header with rich styling
    console.print("\n🚀 [bold cyan]AI-ONE Modern Interface[/bold cyan]")
    console.print("=" * 50, style="cyan")
    console.print(f"[green]Model:[/green] {wrapper.config.model}")
    console.print(f"[green]Tools:[/green] {'Enabled' if wrapper.config.enable_tools else 'Disabled'}")
    
    if wrapper.config.enable_tools:
        stats = wrapper.get_usage_stats()
        tool_count = stats['tools'].get('available_count', 0)
        console.print(f"[green]Available tools:[/green] {tool_count}")
    
    console.print("\n[dim]Type 'quit', 'exit', or 'q' to exit[/dim]")
    console.print("[dim]Type '/stats' to see usage statistics[/dim]")
    console.print("[dim]Type '/sessions' to list active sessions[/dim]")
    console.print("[dim]Type '/help' for more commands[/dim]")
    console.print("-" * 50, style="cyan")
    
    session_id = None
    
    try:
        while True:
            if session_id:
                console.print(f"[blue][{session_id[:8]}...] You:[/blue] ", end="")
                user_input = input()
            else:
                console.print("[blue]👤 You:[/blue] ", end="")
                user_input = input()
            
            if not user_input.strip():
                continue
            
            # Handle special commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                console.print("\n👋 [yellow]Goodbye![/yellow]")
                break
            
            elif user_input == '/stats':
                stats = wrapper.get_usage_stats()
                console.print("\n📊 [bold]Usage Statistics:[/bold]")
                console.print(f"  [green]Sessions:[/green] {stats['sessions']['total_count']} active")
                console.print(f"  [green]Total requests:[/green] {stats['sessions']['total_requests']}")
                if wrapper.config.enable_tools:
                    console.print(f"  [green]Available tools:[/green] {stats['tools']['available_count']}")
                console.print()
                continue
            
            elif user_input == '/sessions':
                sessions = wrapper.list_sessions()
                if sessions:
                    console.print(f"\n📋 [bold]Active Sessions ({len(sessions)}):[/bold]")
                    for session in sessions:
                        console.print(f"  {session['session_id'][:8]}... - {session['stats'].get('requests_count', 0)} requests")
                else:
                    console.print("\n📋 [dim]No active sessions[/dim]")
                console.print()
                continue
            
            elif user_input == '/help':
                console.print("\n🔧 [bold]Available Commands:[/bold]")
                console.print("  [cyan]/stats[/cyan]     - Show usage statistics")
                console.print("  [cyan]/sessions[/cyan]  - List active sessions")
                console.print("  [cyan]/new[/cyan]       - Start new session")
                console.print("  [cyan]/help[/cyan]      - Show this help")
                console.print("  [cyan]quit/exit[/cyan]  - Exit the interface")
                console.print()
                continue
            
            elif user_input == '/new':
                session_id = None
                console.print("🔄 [yellow]Starting new session...[/yellow]")
                continue
            
            # Send question to AI-ONE with git-style status
            try:
                git_display = GitStyleStatusDisplay(console)
                
                def progress_callback(message: str, msg_type: str):
                    """Handle status updates from AI-ONE execution."""
                    if msg_type == "session":
                        git_display.add_step("⚡ Creating new session", "session")
                    elif msg_type == "system_prompt":
                        git_display.add_step("⚡ Loading system prompt", "system")  
                    elif msg_type == "thinking":
                        git_display.add_step("🤔 AI thinking", "thinking")
                    elif msg_type == "workflow_start":
                        git_display.start_workflow()
                        git_display.add_step("⚡ Starting workflow", "workflow")
                    elif msg_type == "tool":
                        # Extract tool name from message
                        if "Using tool:" in message:
                            tool_name = message.replace("Using tool:", "").strip()
                            git_display.add_step(f"🔧 {tool_name}", "tool")
                        else:
                            git_display.add_step(f"🔧 {message}", "tool")
                    elif msg_type == "workflow_end":
                        git_display.end_workflow()
                        git_display.complete_final()
                    elif msg_type == "thinking_complete":
                        git_display.complete_final()
                
                # Start with initial status
                git_display.add_step("📝 Analyzing request", "start")
                
                # Check if git-style method exists (backward compatibility)
                if hasattr(wrapper, 'ask_question_with_git_style'):
                    session_id, response = wrapper.ask_question_with_git_style(
                        user_input, session_id, progress_callback
                    )
                else:
                    # Fallback to regular method
                    session_id, response = wrapper.ask_question(user_input, session_id)
                    git_display.complete_final()
                
                git_display.cleanup()
                console.print(f"\n🤖 [bold green]AI:[/bold green] {response}")
                console.print()
                
            except KeyboardInterrupt:
                if 'git_display' in locals():
                    git_display.cleanup()
                console.print("\n\n⏸️  [yellow]Request interrupted by user[/yellow]")
                continue
            except Exception as e:
                if 'git_display' in locals():
                    git_display.cleanup()
                console.print(f"\n❌ [red]Error:[/red] {e}")
                continue
                
    except KeyboardInterrupt:
        console.print("\n\n👋 [yellow]Goodbye![/yellow]")


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
