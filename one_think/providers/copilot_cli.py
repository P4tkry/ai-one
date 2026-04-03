import subprocess
import uuid
import json
import os
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Union


def ask_question(
    messages: Union[str, List[Dict[str, str]]],
    model: str = 'gpt-4.1',
    session_id: str = None,
    catalog: str = None,
    stream: bool = False
) -> tuple[str | None, str]:
    """
    Ask question via Copilot CLI with JSON messages format.
    
    Args:
        messages: Either plain text (legacy) or list of message objects:
                 [{"author": "system", "message": "system prompt"},
                  {"author": "user", "message": "user prompt"},
                  {"author": "tool", "message": "tool output"}]
        model: LLM model to use
        session_id: Session ID for conversation continuity
        catalog: Working directory
        stream: Enable streaming mode (--stream on)
    
    Returns:
        (session_id, response_text)
    """
    session_id = session_id or str(uuid.uuid4())

    # Handle both legacy string format and new JSON format
    if isinstance(messages, str):
        # Legacy mode: plain text prompt
        command = [
            "copilot",
            f'--resume={session_id}',
            '--model', model,
            '-sp', messages
        ]
        temp_file = None
    else:
        # New mode: JSON messages format
        messages_json = json.dumps(messages, ensure_ascii=False)
        
        # Check if payload is too large for Windows command line (safety margin: 30KB)
        if len(messages_json) > 30000:
            # Use temporary file approach
            temp_file = Path(tempfile.gettempdir()) / f"aione-{session_id}-{int(time.time() * 1000)}.json"
            try:
                # Create enhanced JSON with file processing instructions
                enhanced_messages = [
                    {
                        "author": "system", 
                        "message": "This file contains AI-ONE conversation data due to large payload. Process the following messages in order and continue the conversation based on the context provided. Follow your standard JSON response format after analyzing the conversation history."
                    }
                ] + messages
                
                # Create temp file with enhanced content
                enhanced_json = json.dumps(enhanced_messages, ensure_ascii=False, indent=2)
                temp_file.write_text(enhanced_json, encoding='utf-8')
                
                # Verify file is accessible and readable
                if not temp_file.exists() or not os.access(temp_file, os.R_OK):
                    raise PermissionError("Temp file not accessible")
                    
                command = [
                    "copilot",
                    f'--resume={session_id}',
                    '--model', model,
                    '--add-dir', str(temp_file.parent),  # Allow temp dir access
                    '-sp', f'<<input_file>>{temp_file}<</input_file>>'  # Use Copilot input_file syntax
                ]
            except (OSError, PermissionError) as e:
                # Fallback: cleanup and use direct approach (may fail for very large payloads)
                if temp_file.exists():
                    temp_file.unlink()
                if os.getenv("DEBUG"):
                    print(f"Warning: Temp file approach failed ({e}), falling back to direct")
                command = [
                    "copilot",
                    f'--resume={session_id}',
                    '--model', model,
                    '-sp', messages_json[:25000] + "\n...truncated for command line limits..."
                ]
                temp_file = None
        else:
            # Direct argument approach (original)
            command = [
                "copilot",
                f'--resume={session_id}',
                '--model', model,
                '-sp', messages_json
            ]
            temp_file = None
    
    # Add streaming option if enabled
    if stream:
        command.extend(['--stream', 'on'])

    # Debug: show command only in debug mode  
    # Note: Disable debug output during status tracking for clean UI
    if os.getenv("DEBUG") and not os.getenv("AI_ONE_UI_MODE"):
        print("COMMAND:", command)
        # Note: JSON MESSAGES debug output removed - too verbose

    try:
        result = subprocess.run(
            command,
            cwd=catalog,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"copilot failed (code {result.returncode})\n"
                f"STDERR:\n{result.stderr}\n"
                f"STDOUT:\n{result.stdout}"
            )

        return session_id, result.stdout.strip()
        
    finally:
        # Cleanup temporary file if it was used
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as e:
                # Log but don't fail - temp files will be cleaned by OS eventually
                if os.getenv("DEBUG"):
                    print(f"Warning: Failed to cleanup temp file {temp_file}: {e}")


# Helper function to build messages
def build_messages(
    system_prompt: str = None,
    user_message: str = None,
    tool_results: List[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Build messages array in standard format.
    
    Returns:
        List of message objects with 'author' and 'message' fields
    """
    messages = []
    
    if system_prompt:
        messages.append({
            "author": "system",
            "message": system_prompt
        })
    
    if user_message:
        messages.append({
            "author": "user", 
            "message": user_message
        })
    
    if tool_results:
        for tool_result in tool_results:
            messages.append({
                "author": "tool",
                "message": json.dumps(tool_result, ensure_ascii=False)
            })
    
    return messages


# debug
if __name__ == '__main__':
    # Test new JSON format
    messages = build_messages(
        system_prompt="You are a helpful assistant.",
        user_message="What is the capital of France?"
    )
    session_id, answer = ask_question(messages)
    print(f"Session: {session_id}")
    print(f"Answer: {answer}")