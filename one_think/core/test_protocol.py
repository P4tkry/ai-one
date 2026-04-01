"""
Unit tests for Protocol parsing and validation.
"""

import pytest
import json
from one_think.core.protocol import (
    ProtocolParser,
    ProtocolValidator,
    Response,
    ToolRequest,
    SystemRefreshRequest,
    ToolCall,
    ResponseType,
    parse_llm_response,
)


class TestResponse:
    """Test Response protocol object."""
    
    def test_create_response(self):
        """Should create Response object."""
        resp = Response(content="Hello, world!")
        assert resp.type == ResponseType.RESPONSE
        assert resp.content == "Hello, world!"
    
    def test_response_type_frozen(self):
        """Type should be frozen to RESPONSE."""
        resp = Response(content="test")
        assert resp.type == "response"


class TestToolCall:
    """Test ToolCall validation."""
    
    def test_create_tool_call(self):
        """Should create ToolCall with params."""
        call = ToolCall(
            tool_name="web_fetch",
            params={"url": "https://example.com"},
            id="req_001"
        )
        assert call.tool_name == "web_fetch"
        assert call.params["url"] == "https://example.com"
        assert call.id == "req_001"
    
    def test_empty_tool_name(self):
        """Should reject empty tool_name."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ToolCall(tool_name="   ", params={})
    
    def test_default_params(self):
        """Should default to empty dict."""
        call = ToolCall(tool_name="test")
        assert call.params == {}


class TestToolRequest:
    """Test ToolRequest protocol object."""
    
    def test_create_tool_request(self):
        """Should create ToolRequest with tools."""
        tools = [
            ToolCall(tool_name="web_fetch", params={"url": "test.com"})
        ]
        req = ToolRequest(tools=tools)
        assert req.type == ResponseType.TOOL_REQUEST
        assert len(req.tools) == 1
        assert req.tools[0].tool_name == "web_fetch"
    
    def test_empty_tools_list(self):
        """Should reject empty tools list."""
        with pytest.raises(ValueError, match="(cannot be empty|too_short|at least 1)"):
            ToolRequest(tools=[])
    
    def test_multiple_tools(self):
        """Should accept multiple tools."""
        tools = [
            ToolCall(tool_name="tool1", params={}),
            ToolCall(tool_name="tool2", params={"key": "value"}),
        ]
        req = ToolRequest(tools=tools)
        assert len(req.tools) == 2


class TestSystemRefreshRequest:
    """Test SystemRefreshRequest protocol object."""
    
    def test_create_refresh_request(self):
        """Should create refresh request."""
        req = SystemRefreshRequest(reason="Context window full")
        assert req.type == ResponseType.SYSTEM_REFRESH_REQUEST
        assert req.reason == "Context window full"
    
    def test_optional_reason(self):
        """Reason should be optional."""
        req = SystemRefreshRequest()
        assert req.reason is None


class TestProtocolParser:
    """Test ProtocolParser."""
    
    def test_parse_response(self):
        """Should parse response type."""
        json_str = '{"type": "response", "content": "Hello!"}'
        parsed = ProtocolParser.parse(json_str)
        assert isinstance(parsed, Response)
        assert parsed.content == "Hello!"
    
    def test_parse_tool_request(self):
        """Should parse tool_request type."""
        json_str = '''
        {
            "type": "tool_request",
            "tools": [
                {
                    "tool_name": "web_fetch",
                    "params": {"url": "test.com"},
                    "id": "req_001"
                }
            ]
        }
        '''
        parsed = ProtocolParser.parse(json_str)
        assert isinstance(parsed, ToolRequest)
        assert len(parsed.tools) == 1
        assert parsed.tools[0].tool_name == "web_fetch"
    
    def test_parse_system_refresh(self):
        """Should parse system_refresh_request type."""
        json_str = '{"type": "system_refresh_request", "reason": "drift detected"}'
        parsed = ProtocolParser.parse(json_str)
        assert isinstance(parsed, SystemRefreshRequest)
        assert parsed.reason == "drift detected"
    
    def test_invalid_json(self):
        """Should raise on invalid JSON."""
        with pytest.raises(ValueError, match="not valid JSON"):
            ProtocolParser.parse("not json {")
    
    def test_not_dict(self):
        """Should raise if JSON is not object."""
        with pytest.raises(ValueError, match="must be JSON object"):
            ProtocolParser.parse('["array", "not", "object"]')
    
    def test_missing_type(self):
        """Should raise if 'type' field missing."""
        with pytest.raises(ValueError, match='missing required field "type"'):
            ProtocolParser.parse('{"content": "test"}')
    
    def test_unknown_type(self):
        """Should raise on unknown type."""
        with pytest.raises(ValueError, match="Unknown response type"):
            ProtocolParser.parse('{"type": "unknown_type"}')
    
    def test_is_tool_request(self):
        """Should detect tool requests."""
        resp = Response(content="test")
        req = ToolRequest(tools=[ToolCall(tool_name="test")])
        
        assert not ProtocolParser.is_tool_request(resp)
        assert ProtocolParser.is_tool_request(req)
    
    def test_is_final_response(self):
        """Should detect final responses."""
        resp = Response(content="test")
        req = ToolRequest(tools=[ToolCall(tool_name="test")])
        
        assert ProtocolParser.is_final_response(resp)
        assert not ProtocolParser.is_final_response(req)


class TestProtocolValidator:
    """Test ProtocolValidator."""
    
    def test_validate_tool_name_valid(self):
        """Should accept valid tool names."""
        valid_names = [
            "web_fetch",
            "tool123",
            "MyTool",
            "a",
            "very_long_but_valid_tool_name_here",
        ]
        for name in valid_names:
            assert ProtocolValidator.validate_tool_name(name), f"Should accept: {name}"
    
    def test_validate_tool_name_invalid(self):
        """Should reject invalid tool names."""
        invalid_names = [
            "_private",  # starts with underscore
            "123tool",  # starts with number
            "tool-name",  # contains hyphen
            "tool name",  # contains space
            "",  # empty
            "a" * 51,  # too long
        ]
        for name in invalid_names:
            assert not ProtocolValidator.validate_tool_name(name), f"Should reject: {name}"
    
    def test_validate_request_id_valid(self):
        """Should accept valid request IDs."""
        valid_ids = [
            "req_001",
            "request-123",
            "abc_DEF-456",
            "a",
        ]
        for req_id in valid_ids:
            assert ProtocolValidator.validate_request_id(req_id), f"Should accept: {req_id}"
    
    def test_validate_request_id_invalid(self):
        """Should reject invalid request IDs."""
        invalid_ids = [
            "",  # empty
            "req 001",  # space
            "req@001",  # special char
            "a" * 101,  # too long
        ]
        for req_id in invalid_ids:
            assert not ProtocolValidator.validate_request_id(req_id), f"Should reject: {req_id}"
    
    def test_validate_tool_request_valid(self):
        """Should validate valid tool request."""
        req = ToolRequest(tools=[
            ToolCall(tool_name="web_fetch", params={"url": "test.com"}, id="req_001")
        ])
        is_valid, error = ProtocolValidator.validate_tool_request(req)
        assert is_valid
        assert error is None
    
    def test_validate_tool_request_invalid_name(self):
        """Should catch invalid tool name."""
        req = ToolRequest(tools=[
            ToolCall(tool_name="_invalid", params={})
        ])
        is_valid, error = ProtocolValidator.validate_tool_request(req)
        assert not is_valid
        assert "Invalid tool_name format" in error
    
    def test_validate_tool_request_invalid_id(self):
        """Should catch invalid request ID."""
        req = ToolRequest(tools=[
            ToolCall(tool_name="test", params={}, id="invalid id")
        ])
        is_valid, error = ProtocolValidator.validate_tool_request(req)
        assert not is_valid
        assert "Invalid request ID format" in error


class TestConvenienceFunction:
    """Test parse_llm_response convenience function."""
    
    def test_parse_llm_response(self):
        """Should parse using convenience function."""
        json_str = '{"type": "response", "content": "Test"}'
        parsed = parse_llm_response(json_str)
        assert isinstance(parsed, Response)
        assert parsed.content == "Test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
