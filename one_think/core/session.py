"""
Session management for AI-ONE conversations with GitHub Copilot CLI.

Session provides thin wrapper around Copilot CLI's native session management.
Instead of duplicating conversation history, we leverage Copilot's --resume functionality.

Key changes:
- Session.id maps directly to Copilot CLI --resume session_id
- No message history storage (Copilot CLI handles this)
- Focus on metadata, statistics, and session lifecycle
- Direct integration with copilot --resume={session_id}
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid


class Session:
    """
    Thin wrapper for GitHub Copilot CLI sessions.
    
    This class doesn't store conversation history - that's handled by 
    Copilot CLI via --resume={session_id}. Instead, it manages:
    - Session metadata and preferences
    - Usage statistics and metrics  
    - Session lifecycle (creation, cleanup)
    - Mapping between AI-ONE and Copilot CLI sessions
    
    Attributes:
        id: Session ID that maps to Copilot CLI --resume parameter
        created_at: Session creation timestamp
        metadata: Session metadata (user preferences, config overrides)
        stats: Session usage statistics
        last_activity: Last request timestamp
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize session wrapper.
        
        Args:
            session_id: Custom session ID (generates UUID if not provided)
                       This ID will be passed to copilot --resume={session_id}
            metadata: Session metadata (user preferences, config, etc.)
        """
        self.id: str = session_id or self._generate_session_id()
        self.created_at: datetime = datetime.now(timezone.utc)
        self.metadata: Dict[str, Any] = metadata or {}
        
        # Usage statistics
        self.stats = {
            "requests_count": 0,
            "tool_calls_count": 0,
            "total_tokens_estimated": 0,
            "errors_count": 0,
            "last_model_used": None,
            "session_duration_seconds": 0
        }
        
        # Session state
        self.last_activity: datetime = self.created_at
        self.is_active: bool = True
        
        # Copilot CLI integration
        self.copilot_session_id: str = self.id  # Direct mapping
    
    @staticmethod
    def _generate_session_id() -> str:
        """Generate a unique session ID compatible with Copilot CLI."""
        return str(uuid.uuid4())
    
    def record_request(
        self, 
        model: Optional[str] = None, 
        tool_calls: int = 0,
        estimated_tokens: int = 0,
        had_error: bool = False
    ) -> None:
        """
        Record request statistics.
        
        Args:
            model: LLM model used
            tool_calls: Number of tool calls in request
            estimated_tokens: Estimated token usage
            had_error: Whether request had errors
        """
        self.last_activity = datetime.now(timezone.utc)
        self.stats["requests_count"] += 1
        self.stats["tool_calls_count"] += tool_calls
        self.stats["total_tokens_estimated"] += estimated_tokens
        
        if had_error:
            self.stats["errors_count"] += 1
            
        if model:
            self.stats["last_model_used"] = model
            
        # Update session duration
        duration = (self.last_activity - self.created_at).total_seconds()
        self.stats["session_duration_seconds"] = duration
    
    def get_copilot_session_id(self) -> str:
        """Get session ID for Copilot CLI --resume parameter."""
        return self.copilot_session_id
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set session metadata."""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get session metadata."""
        return self.metadata.get(key, default)
    
    def is_expired(self, max_idle_hours: float = 24.0) -> bool:
        """
        Check if session is expired based on last activity.
        
        Args:
            max_idle_hours: Maximum idle time before expiration
            
        Returns:
            True if session is expired
        """
        if not self.is_active:
            return True
            
        idle_time = datetime.now(timezone.utc) - self.last_activity
        idle_hours = idle_time.total_seconds() / 3600
        return idle_hours > max_idle_hours
    
    def close(self) -> None:
        """Close/deactivate the session."""
        self.is_active = False
        self.last_activity = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata,
            "stats": self.stats,
            "is_active": self.is_active,
            "copilot_session_id": self.copilot_session_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create session from dictionary."""
        session = cls(session_id=data["id"], metadata=data.get("metadata", {}))
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.last_activity = datetime.fromisoformat(data["last_activity"])
        session.stats = data.get("stats", {})
        session.is_active = data.get("is_active", True)
        session.copilot_session_id = data.get("copilot_session_id", session.id)
        return session
    
    def get_summary(self) -> Dict[str, Any]:
        """Get session summary for display."""
        duration_minutes = self.stats["session_duration_seconds"] / 60
        return {
            "session_id": self.id,
            "duration_minutes": round(duration_minutes, 1),
            "requests": self.stats["requests_count"],
            "tool_calls": self.stats["tool_calls_count"],
            "errors": self.stats["errors_count"],
            "last_model": self.stats["last_model_used"],
            "is_active": self.is_active,
            "created": self.created_at.strftime("%Y-%m-%d %H:%M")
        }
    
    def __repr__(self) -> str:
        return f"Session(id={self.id}, requests={self.stats['requests_count']}, active={self.is_active})"