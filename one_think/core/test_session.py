"""
Unit tests for Session management.
"""

import pytest
from datetime import datetime, timezone
from one_think.core.session import Session
from one_think.core.message import (
    MessageType,
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    SystemRefreshMessage,
)


class TestSessionCreation:
    """Test session creation and initialization."""
    
    def test_create_session_default_id(self):
        """Should generate session ID if not provided."""
        session = Session()
        assert session.id.startswith("session_")
        assert len(session.id) > 10
    
    def test_create_session_custom_id(self):
        """Should use custom session ID."""
        session = Session(session_id="custom_123")
        assert session.id == "custom_123"
    
    def test_create_session_with_metadata(self):
        """Should accept metadata."""
        metadata = {"user_id": "user_456", "source": "api"}
        session = Session(metadata=metadata)
        assert session.metadata["user_id"] == "user_456"
        assert session.metadata["source"] == "api"
    
    def test_initial_state(self):
        """Should start with empty history."""
        session = Session()
        assert session.get_message_count() == 0
        assert session.history == []
        assert not session.is_system_prompt_sent()
        assert session.get_last_system_refresh() is None


class TestAddMessage:
    """Test adding messages to session."""
    
    def test_add_user_message(self):
        """Should add user message."""
        session = Session()
        msg = session.add_user_message("Hello!")
        
        assert session.get_message_count() == 1
        assert msg.type == MessageType.USER
        assert msg.content == "Hello!"
        assert session.history[0] == msg
    
    def test_add_assistant_message(self):
        """Should add assistant message."""
        session = Session()
        msg = session.add_assistant_message("Hi there!")
        
        assert session.get_message_count() == 1
        assert msg.type == MessageType.ASSISTANT
        assert msg.content == "Hi there!"
    
    def test_add_tool_result(self):
        """Should add tool result message."""
        session = Session()
        msg = session.add_tool_result(
            content='{"data": "test"}',
            tool_name="web_fetch",
            status="success",
            request_id="req_001"
        )
        
        assert session.get_message_count() == 1
        assert msg.type == MessageType.TOOL_RESULT
        assert msg.tool_name == "web_fetch"
        assert msg.status == "success"
    
    def test_add_multiple_messages(self):
        """Should maintain message order."""
        session = Session()
        
        session.add_user_message("First")
        session.add_assistant_message("Second")
        session.add_user_message("Third")
        
        assert session.get_message_count() == 3
        assert session.history[0].content == "First"
        assert session.history[1].content == "Second"
        assert session.history[2].content == "Third"
    
    def test_add_system_message_updates_state(self):
        """Should track system prompt sent."""
        session = Session()
        assert not session.is_system_prompt_sent()
        
        msg = SystemMessage(content="System prompt")
        session.add_message(msg)
        
        assert session.is_system_prompt_sent()
    
    def test_add_system_refresh_updates_state(self):
        """Should track system refresh timestamp."""
        session = Session()
        assert session.get_last_system_refresh() is None
        
        msg = SystemRefreshMessage(content="Refreshed", reason="drift")
        session.add_message(msg)
        
        assert session.get_last_system_refresh() is not None
        assert isinstance(session.get_last_system_refresh(), datetime)


class TestGetHistory:
    """Test retrieving message history."""
    
    def test_get_all_history(self):
        """Should return all messages."""
        session = Session()
        session.add_user_message("One")
        session.add_assistant_message("Two")
        session.add_user_message("Three")
        
        history = session.get_history()
        assert len(history) == 3
    
    def test_get_history_by_type(self):
        """Should filter by message type."""
        session = Session()
        session.add_user_message("User 1")
        session.add_assistant_message("Assistant 1")
        session.add_user_message("User 2")
        session.add_assistant_message("Assistant 2")
        
        user_msgs = session.get_history(message_type=MessageType.USER)
        assert len(user_msgs) == 2
        assert all(m.type == MessageType.USER for m in user_msgs)
        
        assistant_msgs = session.get_history(message_type=MessageType.ASSISTANT)
        assert len(assistant_msgs) == 2
        assert all(m.type == MessageType.ASSISTANT for m in assistant_msgs)
    
    def test_get_history_with_limit(self):
        """Should limit to most recent messages."""
        session = Session()
        for i in range(10):
            session.add_user_message(f"Message {i}")
        
        recent = session.get_history(limit=3)
        assert len(recent) == 3
        assert recent[0].content == "Message 7"
        assert recent[2].content == "Message 9"
    
    def test_get_history_type_and_limit(self):
        """Should filter by type and limit."""
        session = Session()
        session.add_user_message("User 1")
        session.add_assistant_message("Assistant 1")
        session.add_user_message("User 2")
        session.add_assistant_message("Assistant 2")
        session.add_user_message("User 3")
        
        recent_users = session.get_history(message_type=MessageType.USER, limit=2)
        assert len(recent_users) == 2
        assert recent_users[0].content == "User 2"
        assert recent_users[1].content == "User 3"


class TestConvenienceMethods:
    """Test convenience methods for querying messages."""
    
    def test_get_user_messages(self):
        """Should get all user messages."""
        session = Session()
        session.add_user_message("User 1")
        session.add_assistant_message("Assistant 1")
        session.add_user_message("User 2")
        
        users = session.get_user_messages()
        assert len(users) == 2
        assert all(isinstance(m, UserMessage) for m in users)
    
    def test_get_assistant_messages(self):
        """Should get all assistant messages."""
        session = Session()
        session.add_user_message("User")
        session.add_assistant_message("Assistant 1")
        session.add_assistant_message("Assistant 2")
        
        assistants = session.get_assistant_messages()
        assert len(assistants) == 2
    
    def test_get_tool_results(self):
        """Should get all tool results."""
        session = Session()
        session.add_tool_result('{"a": 1}', "tool1", "success")
        session.add_user_message("User")
        session.add_tool_result('{"b": 2}', "tool2", "success")
        
        tools = session.get_tool_results()
        assert len(tools) == 2
        assert all(isinstance(m, ToolResultMessage) for m in tools)
    
    def test_get_last_message(self):
        """Should get last message overall."""
        session = Session()
        session.add_user_message("First")
        session.add_assistant_message("Last")
        
        last = session.get_last_message()
        assert last.content == "Last"
    
    def test_get_last_message_by_type(self):
        """Should get last message of specific type."""
        session = Session()
        session.add_user_message("User 1")
        session.add_assistant_message("Assistant 1")
        session.add_user_message("User 2")
        session.add_assistant_message("Assistant 2")
        
        last_user = session.get_last_message(message_type=MessageType.USER)
        assert last_user.content == "User 2"
        
        last_assistant = session.get_last_message(message_type=MessageType.ASSISTANT)
        assert last_assistant.content == "Assistant 2"
    
    def test_get_last_message_empty(self):
        """Should return None if no messages."""
        session = Session()
        assert session.get_last_message() is None


class TestMessageCounts:
    """Test message counting methods."""
    
    def test_get_message_count(self):
        """Should count all messages."""
        session = Session()
        assert session.get_message_count() == 0
        
        session.add_user_message("Test")
        assert session.get_message_count() == 1
        
        session.add_assistant_message("Response")
        assert session.get_message_count() == 2
    
    def test_get_message_count_by_type(self):
        """Should count messages grouped by type."""
        session = Session()
        session.add_user_message("User 1")
        session.add_user_message("User 2")
        session.add_assistant_message("Assistant 1")
        session.add_tool_result('{}', "tool", "success")
        
        counts = session.get_message_count_by_type()
        assert counts[MessageType.USER] == 2
        assert counts[MessageType.ASSISTANT] == 1
        assert counts[MessageType.TOOL_RESULT] == 1


class TestSystemRefreshLogic:
    """Test system prompt refresh logic."""
    
    def test_should_refresh_no_system_sent(self):
        """Should suggest refresh if no system prompt sent."""
        session = Session()
        assert session.should_refresh_system_prompt()
    
    def test_should_refresh_too_many_messages(self):
        """Should suggest refresh after many messages."""
        session = Session()
        
        # Send system prompt
        session.add_message(SystemMessage(content="System"))
        assert not session.should_refresh_system_prompt(max_messages_since_refresh=50)
        
        # Add many messages
        for i in range(50):
            session.add_user_message(f"Message {i}")
        
        assert session.should_refresh_system_prompt(max_messages_since_refresh=50)
    
    def test_should_refresh_after_refresh(self):
        """Should reset counter after refresh."""
        session = Session()
        
        # Initial system prompt
        session.add_message(SystemMessage(content="System"))
        
        # Add messages
        for i in range(30):
            session.add_user_message(f"Message {i}")
        
        # Refresh
        session.add_message(SystemRefreshMessage(content="Refreshed"))
        
        # Should not need refresh immediately
        assert not session.should_refresh_system_prompt(max_messages_since_refresh=50)
        
        # Add more messages
        for i in range(50):
            session.add_user_message(f"More {i}")
        
        # Now should need refresh
        assert session.should_refresh_system_prompt(max_messages_since_refresh=50)


class TestSessionSerialization:
    """Test session serialization."""
    
    def test_to_dict(self):
        """Should serialize to dict."""
        session = Session(session_id="test_123")
        session.add_user_message("Hello")
        session.add_assistant_message("Hi")
        
        data = session.to_dict()
        
        assert data["id"] == "test_123"
        assert data["message_count"] == 2
        assert "created_at" in data
        assert "message_counts_by_type" in data
    
    def test_repr(self):
        """Should have readable repr."""
        session = Session(session_id="test_456")
        session.add_user_message("Test")
        
        repr_str = repr(session)
        assert "test_456" in repr_str
        assert "messages=1" in repr_str


class TestClearHistory:
    """Test clearing session history."""
    
    def test_clear_history(self):
        """Should clear all messages and reset state."""
        session = Session()
        session.add_message(SystemMessage(content="System"))
        session.add_user_message("User")
        session.add_assistant_message("Assistant")
        
        assert session.get_message_count() == 3
        assert session.is_system_prompt_sent()
        
        session.clear_history()
        
        assert session.get_message_count() == 0
        assert not session.is_system_prompt_sent()
        assert session.get_last_system_refresh() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
