"""
AI-ONE Entry Point

This script provides both modern and legacy interfaces:
- By default: Modern interface with session management and tool registry
- With --legacy: Original simple interface

Usage:
    python main.py                    # Modern interface (recommended)
    python main.py --legacy           # Legacy interface  
    python main.py --no-tools         # Modern without tools
    python main.py --model claude-4   # Specify model
"""

from one_think.main_modern import main

if __name__ == "__main__":
    main()

