"""
Message types and validation for AI-ONE conversation system.

This module defines the core Message hierarchy with strict validation using Pydantic.
All messages are type-safe and automatically validated.

Security: User messages are automatically sanitized to prevent prompt injection.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import re
import unicodedata
from pydantic import BaseModel, Field, field_validator, ConfigDict


# Security: Reserved separators that must be filtered from untrusted input
PROMPT_SEPARATORS = [
    '<<<BEGIN OF USER UNTRUSTED DATA>>>',
    '<<<END OF USER UNTRUSTED DATA>>>',
    '<<<BEGIN OF SYSTEM TRUSTED DATA>>>',
    '<<<END OF SYSTEM TRUSTED DATA>>>',
    '<<<BEGIN OF TOOL EXECUTION STDERR>>>',
    '<<<END OF TOOL EXECUTION STDERR>>>',
    '<<<BEGIN OF TOOL EXECUTION STDOUT>>>',
    '<<<END OF TOOL EXECUTION STDOUT>>>',
]

# Security: Patterns that indicate possible prompt injection attempts
INJECTION_PATTERNS = [
    r'<<<BEGIN OF.*?>>>',
    r'<<<END OF.*?>>>',
    r'IGNORE\s+(PREVIOUS|ALL|ABOVE)\s+INSTRUCTIONS?',
    r'NEW\s+SYSTEM\s+PROMPT:?',
    r'YOU\s+ARE\s+NOW',
    r'OVERRIDE\s+SYSTEM',
    r'\[SYSTEM\]',
    r'\[ASSISTANT\]',
    r'"type"\s*:\s*"system"',
    r'"role"\s*:\s*"system"',
]


def sanitize_untrusted_input(text: str) -> str:
    """
    Multi-layer sanitization for untrusted user input.
    
    Defends against prompt injection by:
    1. Removing reserved prompt separators
    2. Detecting and filtering injection patterns
    3. Normalizing unicode to prevent obfuscation
    
    Args:
        text: Raw untrusted input
        
    Returns:
        Sanitized text safe for inclusion in prompts
    """
    if not text:
        return ""
    
    # Layer 1: Remove separators
    sanitized = str(text)
    for separator in PROMPT_SEPARATORS:
        sanitized = sanitized.replace(separator, "")
    
    # Layer 2: Pattern detection and filtering
    for pattern in INJECTION_PATTERNS:
        sanitized = re.sub(pattern, "[FILTERED]", sanitized, flags=re.IGNORECASE)
    
    # Layer 3: Unicode normalization (prevent unicode obfuscation)
    sanitized = unicodedata.normalize('NFKC', sanitized)
    
    return sanitized


class MessageType(str, Enum):
    """
    Message type enum defining trust boundaries.
    
    Trust model:
    - SYSTEM: Fully trusted, contains instructions
    - USER: Untrusted, automatically sanitized
    - ASSISTANT: LLM output, treated as data
    - TOOL_RESULT: Conditionally trusted, validated
    - SYSTEM_REFRESH: Fully trusted, refreshes instructions
    """
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"
    SYSTEM_REFRESH = "system_refresh"


class Message(BaseModel):
    """
    Base message class with automatic validation.
    
    All messages have:
    - type: MessageType indicating trust level
    - content: Message payload (auto-sanitized for USER type)
    - timestamp: When message was created
    - metadata: Optional additional data
    
    Subclasses add type-specific fields.
    """
    type: MessageType
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        frozen=False,  # Allow mutation for content sanitization
        use_enum_values=True
    )
    
    @field_validator('content')
    @classmethod
    def sanitize_if_untrusted(cls, v: str, info) -> str:
        """
        Automatically sanitize content if message type is USER.
        This is the primary defense against prompt injection.
        """
        # Get the message type from the data being validated
        msg_type = info.data.get('type')
        
        # Sanitize only USER messages (untrusted input)
        if msg_type == MessageType.USER:
            return sanitize_untrusted_input(v)
        
        return v
    
    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary representation."""
        return {
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class SystemMessage(Message):
    """
    System prompt message (fully trusted).
    
    Sent once at the beginning of a conversation to establish:
    - Security rules
    - Behavior guidelines
    - Available tools
    - Response format requirements
    
    Should never be influenced by user input.
    """
    type: MessageType = Field(default=MessageType.SYSTEM, frozen=True)
    
    def __init__(self, content: str, **kwargs):
        super().__init__(type=MessageType.SYSTEM, content=content, **kwargs)


class UserMessage(Message):
    """
    User input message (untrusted, auto-sanitized).
    
    Contains user queries, commands, or responses.
    Content is automatically sanitized to prevent prompt injection.
    
    Trust level: UNTRUSTED
    """
    type: MessageType = Field(default=MessageType.USER, frozen=True)
    
    def __init__(self, content: str, **kwargs):
        super().__init__(type=MessageType.USER, content=content, **kwargs)


class AssistantMessage(Message):
    """
    LLM response message.
    
    Contains:
    - Natural language responses to user
    - Tool requests (structured JSON)
    - System refresh requests
    
    This is parsed to determine next action (respond, call tools, refresh).
    """
    type: MessageType = Field(default=MessageType.ASSISTANT, frozen=True)
    
    def __init__(self, content: str, **kwargs):
        super().__init__(type=MessageType.ASSISTANT, content=content, **kwargs)


class ToolResultMessage(Message):
    """
    Tool execution result message (conditionally trusted).
    
    Contains structured JSON response from tool execution:
    {
        "status": "success" | "error",
        "tool": "tool_name",
        "request_id": "unique_id",
        "result": {...},
        "error": {...} | null,
        "execution_time_ms": 123
    }
    
    Trust level: CONDITIONALLY TRUSTED (validate structure and sanitize data)
    """
    type: MessageType = Field(default=MessageType.TOOL_RESULT, frozen=True)
    tool_name: str
    status: str  # "success" or "error"
    request_id: Optional[str] = None
    execution_time_ms: Optional[float] = None
    
    def __init__(
        self,
        content: str,
        tool_name: str,
        status: str,
        request_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        **kwargs
    ):
        super().__init__(
            type=MessageType.TOOL_RESULT,
            content=content,
            tool_name=tool_name,
            status=status,
            request_id=request_id,
            execution_time_ms=execution_time_ms,
            **kwargs
        )
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Ensure status is valid."""
        if v not in ("success", "error"):
            raise ValueError(f"status must be 'success' or 'error', got: {v}")
        return v
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with tool-specific fields."""
        base = super().to_dict()
        base.update({
            "tool_name": self.tool_name,
            "status": self.status,
            "request_id": self.request_id,
            "execution_time_ms": self.execution_time_ms,
        })
        return base


class SystemRefreshMessage(Message):
    """
    System prompt refresh message (fully trusted).
    
    Sent when LLM requests a refresh of system instructions.
    Used to re-inject system prompt mid-conversation if:
    - Context window is getting full
    - LLM needs to recall guidelines
    - Behavior drift detected
    
    Trust level: TRUSTED
    """
    type: MessageType = Field(default=MessageType.SYSTEM_REFRESH, frozen=True)
    reason: Optional[str] = None
    
    def __init__(self, content: str, reason: Optional[str] = None, **kwargs):
        super().__init__(
            type=MessageType.SYSTEM_REFRESH,
            content=content,
            reason=reason,
            **kwargs
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with reason."""
        base = super().to_dict()
        base["reason"] = self.reason
        return base


# Type hints for convenience
AnyMessage = SystemMessage | UserMessage | AssistantMessage | ToolResultMessage | SystemRefreshMessage
