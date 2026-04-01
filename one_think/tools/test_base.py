"""
Unit tests for Tool base class and response format.
"""

import pytest
import time
from one_think.tools.base import Tool, ToolResponse, ToolError, ToolLegacy


class MockTool(Tool):
    """Mock tool for testing."""
    
    name = "mock_tool"
    description = "A mock tool for testing"
    
    def execute_json(self, params, request_id=None):
        """Simple mock execution."""
        if params.get("should_error"):
            return self._create_error_response(
                error_type="MockError",
                message="Intentional error for testing",
                request_id=request_id
            )
        
        return self._create_success_response(
            result={"data": params.get("input", "default")},
            request_id=request_id,
            execution_time_ms=10.5
        )
    
    def get_help(self):
        """Return help text."""
        return "Mock tool help text"


class TestToolResponse:
    """Test ToolResponse model."""
    
    def test_create_success_response(self):
        """Should create success response."""
        resp = ToolResponse(
            status="success",
            tool="test_tool",
            result={"data": "test"},
            execution_time_ms=42.0
        )
        
        assert resp.status == "success"
        assert resp.tool == "test_tool"
        assert resp.result["data"] == "test"
        assert resp.error is None
        assert resp.execution_time_ms == 42.0
    
    def test_create_error_response(self):
        """Should create error response."""
        resp = ToolResponse(
            status="error",
            tool="test_tool",
            error={
                "type": "TestError",
                "message": "Something went wrong"
            },
            execution_time_ms=15.0
        )
        
        assert resp.status == "error"
        assert resp.result is None
        assert resp.error["type"] == "TestError"
    
    def test_status_validation(self):
        """Should validate status is success or error."""
        with pytest.raises(ValueError):
            ToolResponse(
                status="invalid",
                tool="test",
                execution_time_ms=0
            )
    
    def test_to_json(self):
        """Should serialize to JSON."""
        resp = ToolResponse(
            status="success",
            tool="test",
            result={"key": "value"},
            execution_time_ms=10.0
        )
        
        json_str = resp.to_json()
        assert "success" in json_str
        assert "test" in json_str
        assert "key" in json_str
    
    def test_to_dict(self):
        """Should convert to dict."""
        resp = ToolResponse(
            status="success",
            tool="test",
            result={"data": 123},
            execution_time_ms=5.0,
            request_id="req_001"
        )
        
        data = resp.to_dict()
        assert data["status"] == "success"
        assert data["tool"] == "test"
        assert data["result"]["data"] == 123
        assert data["request_id"] == "req_001"


class TestToolError:
    """Test ToolError model."""
    
    def test_create_tool_error(self):
        """Should create tool error."""
        error = ToolError(
            type="NetworkError",
            message="Connection failed",
            details={"host": "example.com", "port": 443}
        )
        
        assert error.type == "NetworkError"
        assert error.message == "Connection failed"
        assert error.details["host"] == "example.com"


class TestToolBase:
    """Test Tool base class."""
    
    def test_must_set_name(self):
        """Should require name to be set."""
        class BadTool(Tool):
            # Doesn't set name
            def execute_json(self, params, request_id=None):
                pass
            def get_help(self):
                pass
        
        with pytest.raises(NotImplementedError, match="unique 'name'"):
            BadTool()
    
    def test_mock_tool_success(self):
        """Should execute successfully."""
        tool = MockTool()
        resp = tool(params={"input": "test_value"}, request_id="req_123")
        
        assert resp.status == "success"
        assert resp.tool == "mock_tool"
        assert resp.result["data"] == "test_value"
        assert resp.request_id == "req_123"
        assert resp.execution_time_ms > 0
    
    def test_mock_tool_error(self):
        """Should return error response."""
        tool = MockTool()
        resp = tool(params={"should_error": True}, request_id="req_456")
        
        assert resp.status == "error"
        assert resp.tool == "mock_tool"
        assert resp.error["type"] == "MockError"
        assert resp.result is None
    
    def test_help_request(self):
        """Should return help when help=true."""
        tool = MockTool()
        resp = tool(params={"help": True})
        
        assert resp.status == "success"
        assert resp.result["help"] == "Mock tool help text"
        assert resp.metadata.get("is_help") is True
    
    def test_callable_interface(self):
        """Should be callable."""
        tool = MockTool()
        resp = tool({"input": "via_call"})
        
        assert resp.status == "success"
        assert resp.result["data"] == "via_call"
    
    def test_exception_handling(self):
        """Should catch unhandled exceptions."""
        class BrokenTool(Tool):
            name = "broken_tool"
            description = "Tool that raises"
            
            def execute_json(self, params, request_id=None):
                raise RuntimeError("Oops!")
            
            def get_help(self):
                return "Help"
        
        tool = BrokenTool()
        resp = tool(params={})
        
        assert resp.status == "error"
        assert resp.error["type"] == "UnhandledException"
        assert "RuntimeError" in resp.error["message"]


class TestToolHelpers:
    """Test Tool helper methods."""
    
    def test_create_success_response(self):
        """Should create success response."""
        tool = MockTool()
        resp = tool._create_success_response(
            result={"key": "value"},
            request_id="req_001",
            execution_time_ms=25.0
        )
        
        assert resp.status == "success"
        assert resp.result["key"] == "value"
        assert resp.request_id == "req_001"
        assert resp.execution_time_ms == 25.0
    
    def test_create_error_response(self):
        """Should create error response."""
        tool = MockTool()
        resp = tool._create_error_response(
            error_type="ValidationError",
            message="Invalid input",
            details={"field": "url"},
            request_id="req_002"
        )
        
        assert resp.status == "error"
        assert resp.error["type"] == "ValidationError"
        assert resp.error["message"] == "Invalid input"
        assert resp.error["details"]["field"] == "url"
    
    def test_validate_required_params_success(self):
        """Should pass validation with all params."""
        tool = MockTool()
        params = {"url": "test.com", "timeout": 10}
        
        error_resp = tool.validate_required_params(params, ["url", "timeout"])
        assert error_resp is None
    
    def test_validate_required_params_missing(self):
        """Should return error for missing params."""
        tool = MockTool()
        params = {"url": "test.com"}
        
        error_resp = tool.validate_required_params(params, ["url", "timeout"])
        assert error_resp is not None
        assert error_resp.status == "error"
        assert error_resp.error["type"] == "MissingParameters"
        assert "timeout" in error_resp.error["message"]


class TestToolString:
    """Test Tool string representations."""
    
    def test_str(self):
        """Should have readable string."""
        tool = MockTool()
        s = str(tool)
        
        assert "mock_tool" in s
        assert "mock tool for testing" in s.lower()
        assert "help" in s.lower()
    
    def test_repr(self):
        """Should have developer repr."""
        tool = MockTool()
        r = repr(tool)
        
        assert "Tool" in r
        assert "mock_tool" in r


class TestLegacyToolWrapper:
    """Test backward compatibility wrapper."""
    
    def test_legacy_tool_success(self):
        """Should wrap old execute() to JSON."""
        class OldTool(ToolLegacy):
            name = "old_tool"
            description = "Legacy tool"
            
            def execute(self, arguments=None):
                return "output data", ""
        
        tool = OldTool()
        resp = tool(params={})
        
        assert resp.status == "success"
        assert resp.result["output"] == "output data"
    
    def test_legacy_tool_error(self):
        """Should wrap stderr as error."""
        class OldTool(ToolLegacy):
            name = "old_tool"
            description = "Legacy tool"
            
            def execute(self, arguments=None):
                return "", "Something failed"
        
        tool = OldTool()
        resp = tool(params={})
        
        assert resp.status == "error"
        assert "Something failed" in resp.error["message"]
    
    def test_legacy_tool_exception(self):
        """Should catch exceptions."""
        class OldTool(ToolLegacy):
            name = "old_tool"
            description = "Legacy tool"
            
            def execute(self, arguments=None):
                raise ValueError("Bad value")
        
        tool = OldTool()
        resp = tool(params={})
        
        assert resp.status == "error"
        assert resp.error["type"] == "ValueError"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
