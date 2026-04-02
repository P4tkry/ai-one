import subprocess
import uuid
import json
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
    else:
        # New mode: JSON messages format
        messages_json = json.dumps(messages, ensure_ascii=False)
        command = [
            "copilot",
            f'--resume={session_id}',
            '--model', model,
            '-sp', messages_json
        ]
    
    # Add streaming option if enabled
    if stream:
        command.extend(['--stream', 'on'])

    print("COMMAND:", command)
    
    # Debug: show formatted messages if JSON
    if isinstance(messages, list):
        print("JSON MESSAGES:")
        for i, msg in enumerate(messages):
            print(f"  {i+1}. {msg.get('author', 'unknown')}: {msg.get('message', '')[:100]}...")

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