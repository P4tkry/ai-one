"""
Session management for AI-ONE conversations.

Session tracks:
- Conversation history (all messages)
- System prompt state
- Session metadata
- Message addition and retrieval

This is the central state manager for a conversation.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid
from one_think.core.message import (
    Message,
    AnyMessage,
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    SystemRefreshMessage,
    MessageType,
)


class Session:
    """
    Manages state for a single conversation session.
    
    Responsibilities:
    - Track conversation history
    - Manage system prompt state
    - Provide message querying and filtering
    - Handle session lifecycle
    
    Attributes:
        id: Unique session identifier
        created_at: Session creation timestamp
        history: List of all messages in conversation order
        metadata: Optional session metadata
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """
        Initialize a new conversation session.
        
        Args:
            session_id: Optional custom session ID (generates UUID if not provided)
            metadata: Optional session metadata (e.g., user_id, source)
        """
        self.id: str = session_id or self._generate_session_id()
        self.created_at: datetime = datetime.now(timezone.utc)
        self.history: list[AnyMessage] = []
        self.metadata: dict = metadata or {}
        
        # Track whether system prompt has been sent
        self._system_prompt_sent: bool = False
        self._last_system_refresh: Optional[datetime] = None
    
    @staticmethod
    def _generate_session_id() -> str:
        """Generate a unique session ID."""
        return f"session_{uuid.uuid4().hex[:16]}"
    
    def add_message(self, message: AnyMessage) -> None:
        """
        Add a message to conversation history.
        
        Args:
            message: Message to add
        """
        if not isinstance(message, Message):
            raise TypeError(f"Expected Message instance, got {type(message)}")
        
        self.history.append(message)
        
        # Track system prompt state
        if isinstance(message, SystemMessage):
            self._system_prompt_sent = True
        
        if isinstance(message, SystemRefreshMessage):
            self._last_system_refresh = message.timestamp
    
    def add_user_message(self, content: str, **kwargs) -> UserMessage:
        """
        Convenience method to add a user message.
        
        Args:
            content: User message content
            **kwargs: Additional message fields (metadata, etc.)
            
        Returns:
            Created UserMessage
        """
        msg = UserMessage(content=content, **kwargs)
        self.add_message(msg)
        return msg
    
    def add_assistant_message(self, content: str, **kwargs) -> AssistantMessage:
        """
        Convenience method to add an assistant message.
        
        Args:
            content: Assistant response content
            **kwargs: Additional message fields
            
        Returns:
            Created AssistantMessage
        """
        msg = AssistantMessage(content=content, **kwargs)
        self.add_message(msg)
        return msg
    
    def add_tool_result(
        self,
        content: str,
        tool_name: str,
        status: str,
        request_id: Optional[str] = None,
        **kwargs
    ) -> ToolResultMessage:
        """
        Convenience method to add a tool result message.
        
        Args:
            content: Tool result JSON content
            tool_name: Name of tool that was executed
            status: "success" or "error"
            request_id: Optional request identifier
            **kwargs: Additional message fields
            
        Returns:
            Created ToolResultMessage
        """
        msg = ToolResultMessage(
            content=content,
            tool_name=tool_name,
            status=status,
            request_id=request_id,
            **kwargs
        )
        self.add_message(msg)
        return msg
    
    def get_history(
        self,
        message_type: Optional[MessageType] = None,
        limit: Optional[int] = None
    ) -> list[AnyMessage]:
        """
        Get conversation history with optional filtering.
        
        Args:
            message_type: Optional filter by message type
            limit: Optional limit on number of messages (most recent)
            
        Returns:
            List of messages (filtered and/or limited)
        """
        messages = self.history
        
        # Filter by type if specified
        if message_type is not None:
            messages = [m for m in messages if m.type == message_type]
        
        # Apply limit if specified (most recent)
        if limit is not None and limit > 0:
            messages = messages[-limit:]
        
        return messages
    
    def get_last_message(self, message_type: Optional[MessageType] = None) -> Optional[AnyMessage]:
        """
        Get the last message in history.
        
        Args:
            message_type: Optional filter by type
            
        Returns:
            Last message or None if no messages
        """
        messages = self.get_history(message_type=message_type)
        return messages[-1] if messages else None
    
    def get_user_messages(self, limit: Optional[int] = None) -> list[UserMessage]:
        """Get all user messages."""
        return self.get_history(message_type=MessageType.USER, limit=limit)
    
    def get_assistant_messages(self, limit: Optional[int] = None) -> list[AssistantMessage]:
        """Get all assistant messages."""
        return self.get_history(message_type=MessageType.ASSISTANT, limit=limit)
    
    def get_tool_results(self, limit: Optional[int] = None) -> list[ToolResultMessage]:
        """Get all tool result messages."""
        return self.get_history(message_type=MessageType.TOOL_RESULT, limit=limit)
    
    def is_system_prompt_sent(self) -> bool:
        """Check if system prompt has been sent in this session."""
        return self._system_prompt_sent
    
    def get_last_system_refresh(self) -> Optional[datetime]:
        """Get timestamp of last system prompt refresh."""
        return self._last_system_refresh
    
    def should_refresh_system_prompt(self, max_messages_since_refresh: int = 50) -> bool:
        """
        Determine if system prompt should be refreshed.
        
        Criteria:
        - Too many messages since last system prompt
        - Potential drift in behavior
        
        Args:
            max_messages_since_refresh: Max messages before suggesting refresh
            
        Returns:
            True if refresh recommended
        """
        if not self._system_prompt_sent:
            return True
        
        if self._last_system_refresh is None:
            # Count messages since initial system prompt
            messages_since = len(self.history)
        else:
            # Count messages since last refresh
            messages_since = sum(
                1 for m in self.history
                if m.timestamp > self._last_system_refresh
            )
        
        return messages_since >= max_messages_since_refresh
    
    def get_message_count(self) -> int:
        """Get total number of messages in history."""
        return len(self.history)
    
    def get_message_count_by_type(self) -> dict[str, int]:
        """
        Get message counts grouped by type.
        
        Returns:
            Dict of {message_type: count}
        """
        counts = {}
        for message in self.history:
            msg_type = message.type
            counts[msg_type] = counts.get(msg_type, 0) + 1
        return counts
    
    def clear_history(self) -> None:
        """
        Clear conversation history.
        
        Warning: This is destructive and cannot be undone.
        Use for cleanup or reset scenarios.
        """
        self.history.clear()
        self._system_prompt_sent = False
        self._last_system_refresh = None
    
    def to_dict(self) -> dict:
        """
        Serialize session to dictionary.
        
        Returns:
            Dict representation of session
        """
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "message_count": self.get_message_count(),
            "message_counts_by_type": self.get_message_count_by_type(),
            "system_prompt_sent": self._system_prompt_sent,
            "last_system_refresh": (
                self._last_system_refresh.isoformat()
                if self._last_system_refresh else None
            ),
        }
    
    def __repr__(self) -> str:
        """String representation of session."""
        return (
            f"Session(id={self.id}, "
            f"messages={self.get_message_count()}, "
            f"created={self.created_at.isoformat()})"
        )
