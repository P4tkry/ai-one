"""
Messenger Tool - Full JSON migration with Pydantic schemas.
Facebook Messenger integration with structured responses and validation.
"""
import os
import json
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
import requests
from dotenv import load_dotenv

from one_think.tools.base import Tool, ToolResponse

load_dotenv()


class MessengerTool(Tool):
    """
    Facebook Messenger Tool with structured JSON responses and validation.
    
    Note: This is a v2 migration - full functionality needs to be restored.
    """
    
    name = "messenger"
    description = "Send and receive messages via Facebook Messenger."
    version = "2.0.0"
    
    # Pydantic schemas
    class Input(BaseModel):
        """Input parameters for messenger operations."""
        operation: Literal["send", "receive", "get_profile"] = Field(description="Messenger operation")
        recipient_id: Optional[str] = Field(default=None, description="Recipient ID (for send)")
        message: Optional[str] = Field(default=None, description="Message to send")
        user_id: Optional[str] = Field(default=None, description="User ID (for get_profile)")
        
    class Output(BaseModel):
        """Output format for messenger operations."""
        operation: str = Field(description="Operation performed")
        success: bool = Field(description="Whether operation succeeded")
        message_id: Optional[str] = Field(description="Message ID (for send)")
        messages: Optional[List[Dict[str, Any]]] = Field(description="Messages (for receive)")
        profile: Optional[Dict[str, Any]] = Field(description="User profile (for get_profile)")
        error: Optional[str] = Field(description="Error message if failed")
    
    DEFAULT_LIST_LIMIT = 10
    DEFAULT_READ_LIMIT = 20
    MAX_LIMIT = 100
    
    def __init__(self):
        super().__init__()
        self.page_access_token = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN")
        self.page_id = os.getenv("MESSENGER_PAGE_ID")
        self.graph_api_version = os.getenv("MESSENGER_GRAPH_API_VERSION", "v25.0")
        self.base_url = f"https://graph.facebook.com/{self.graph_api_version}"
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute Messenger operation with JSON response."""
        
        # Check configuration
        if not self.page_access_token:
            return self._create_error_response(
                "MESSENGER_PAGE_ACCESS_TOKEN not set in .env file",
                request_id=request_id
            )
        
        if not self.page_id:
            return self._create_error_response(
                "MESSENGER_PAGE_ID not set in .env file",
                request_id=request_id
            )
        
        # Validate operation
        operation = params.get("operation")
        if not operation:
            return self._create_error_response(
                "Missing required parameter: 'operation'",
                request_id=request_id
            )
        
        # Route to operation handlers
        if operation == "send_message":
            return self._send_message(params, request_id)
        elif operation == "list_conversations":
            return self._list_conversations(params, request_id)
        elif operation == "get_conversation":
            return self._get_conversation(params, request_id)
        elif operation == "get_user_profile":
            return self._get_user_profile(params, request_id)
        elif operation == "health":
            return self._health_check(request_id)
        else:
            return self._create_error_response(
                f"Unknown operation: '{operation}'. Valid operations: send_message, list_conversations, get_conversation, get_user_profile, health",
                request_id=request_id
            )
    
    def _send_message(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Send a message via Messenger."""
        recipient_id = params.get("recipient_id")
        message = params.get("message")
        
        if not recipient_id:
            return self._create_error_response(
                "Missing required parameter: 'recipient_id'",
                request_id=request_id
            )
        
        if not message:
            return self._create_error_response(
                "Missing required parameter: 'message'",
                request_id=request_id
            )
        
        try:
            url = f"{self.base_url}/me/messages"
            payload = {
                "recipient": {"id": recipient_id},
                "message": {"text": message},
                "access_token": self.page_access_token
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            return self._create_success_response(
                result={
                    "message_sent": True,
                    "recipient_id": recipient_id,
                    "message": message,
                    "message_id": result.get("message_id"),
                    "api_response": result
                },
                request_id=request_id
            )
            
        except requests.exceptions.RequestException as e:
            return self._create_error_response(
                f"Failed to send message: {e}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Unexpected error sending message: {e}",
                request_id=request_id
            )
    
    def _list_conversations(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """List conversations."""
        limit = min(int(params.get("limit", self.DEFAULT_LIST_LIMIT)), self.MAX_LIMIT)
        
        try:
            url = f"{self.base_url}/{self.page_id}/conversations"
            params_dict = {
                "access_token": self.page_access_token,
                "limit": limit,
                "fields": "id,updated_time,participants"
            }
            
            response = requests.get(url, params=params_dict, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            conversations = result.get("data", [])
            
            return self._create_success_response(
                result={
                    "conversations": conversations,
                    "total_returned": len(conversations),
                    "limit": limit,
                    "paging": result.get("paging", {})
                },
                request_id=request_id
            )
            
        except requests.exceptions.RequestException as e:
            return self._create_error_response(
                f"Failed to list conversations: {e}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Unexpected error listing conversations: {e}",
                request_id=request_id
            )
    
    def _get_conversation(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Get conversation details."""
        conversation_id = params.get("conversation_id")
        if not conversation_id:
            return self._create_error_response(
                "Missing required parameter: 'conversation_id'",
                request_id=request_id
            )
        
        limit = min(int(params.get("limit", self.DEFAULT_READ_LIMIT)), self.MAX_LIMIT)
        
        try:
            url = f"{self.base_url}/{conversation_id}/messages"
            params_dict = {
                "access_token": self.page_access_token,
                "limit": limit,
                "fields": "id,created_time,from,to,message"
            }
            
            response = requests.get(url, params=params_dict, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            messages = result.get("data", [])
            
            return self._create_success_response(
                result={
                    "conversation_id": conversation_id,
                    "messages": messages,
                    "total_returned": len(messages),
                    "limit": limit,
                    "paging": result.get("paging", {})
                },
                request_id=request_id
            )
            
        except requests.exceptions.RequestException as e:
            return self._create_error_response(
                f"Failed to get conversation: {e}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Unexpected error getting conversation: {e}",
                request_id=request_id
            )
    
    def _get_user_profile(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Get user profile information."""
        user_id = params.get("user_id")
        if not user_id:
            return self._create_error_response(
                "Missing required parameter: 'user_id'",
                request_id=request_id
            )
        
        try:
            url = f"{self.base_url}/{user_id}"
            params_dict = {
                "access_token": self.page_access_token,
                "fields": "first_name,last_name,profile_pic"
            }
            
            response = requests.get(url, params=params_dict, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            return self._create_success_response(
                result={
                    "user_id": user_id,
                    "profile": result
                },
                request_id=request_id
            )
            
        except requests.exceptions.RequestException as e:
            return self._create_error_response(
                f"Failed to get user profile: {e}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Unexpected error getting user profile: {e}",
                request_id=request_id
            )
    
    def _health_check(self, request_id: Optional[str]) -> ToolResponse:
        """Check Messenger API health."""
        return self._create_success_response(
            result={
                "status": "configured",
                "page_access_token_set": bool(self.page_access_token),
                "page_id_set": bool(self.page_id),
                "graph_api_version": self.graph_api_version,
                "base_url": self.base_url
            },
            request_id=request_id
        )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return """Messenger Tool

DESCRIPTION:
    Send and receive messages via Facebook Messenger.
    Migrated to v2 JSON format with core functionality preserved.

OPERATIONS:
    send_message        - Send a message to a user
    list_conversations  - List page conversations
    get_conversation    - Get conversation messages
    get_user_profile    - Get user profile information
    health             - Check API configuration

PARAMETERS:
    operation (string, required)
        Operation to perform

    For send_message:
        recipient_id (string, required) - User ID to send message to
        message (string, required) - Message text to send

    For list_conversations:
        limit (integer, optional) - Number of conversations to return (default: 10, max: 100)

    For get_conversation:
        conversation_id (string, required) - Conversation ID to retrieve
        limit (integer, optional) - Number of messages to return (default: 20, max: 100)

    For get_user_profile:
        user_id (string, required) - User ID to get profile for

EXAMPLES:
    1. Send message:
       {"operation": "send_message", "recipient_id": "123456789", "message": "Hello!"}

    2. List conversations:
       {"operation": "list_conversations", "limit": 5}

    3. Get conversation:
       {"operation": "get_conversation", "conversation_id": "t_123456789", "limit": 10}

    4. Get user profile:
       {"operation": "get_user_profile", "user_id": "123456789"}

    5. Health check:
       {"operation": "health"}

CONFIGURATION:
    Set in .env file:
        MESSENGER_PAGE_ACCESS_TOKEN=your_page_access_token
        MESSENGER_PAGE_ID=your_page_id
        MESSENGER_GRAPH_API_VERSION=v25.0  # optional

RESPONSE FORMAT:
    Success:
        {
            "status": "success",
            "result": {
                "message_sent": true,
                "recipient_id": "123456789",
                "message": "Hello!",
                "message_id": "m_abc123"
            }
        }
    
    Error:
        {
            "status": "error",
            "error": {
                "message": "Error description",
                "type": "ToolExecutionError"
            }
        }

NOTES:
    - Requires Facebook Page Access Token
    - Works with Facebook Pages API
    - Supports basic messaging operations
    - Rate limiting handled by Facebook
    - All responses now in structured JSON format
"""