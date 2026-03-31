from one_think.tools import Tool
import os
import json
from typing import Tuple, Any, Dict, Optional, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()


class MessengerTool(Tool):
    """
    Facebook Messenger Tool

    Supported operations:
    - send_message
    - list_conversations
    - get_conversation
    - read_conversation
    - get_message
    - get_user_profile
    - health
    - help

    Required environment variables:
    - MESSENGER_PAGE_ACCESS_TOKEN
    - MESSENGER_PAGE_ID

    Optional environment variables:
    - MESSENGER_GRAPH_API_VERSION (default: v25.0)
    - MESSENGER_REQUEST_TIMEOUT (default: 20)
    """

    name = "messenger"
    description = "Send and receive messages via Facebook Messenger. (use always when refer to messenger)"

    DEFAULT_LIST_LIMIT = 10
    DEFAULT_READ_LIMIT = 20
    MAX_LIMIT = 100
    MAX_MESSAGE_DETAILS_LIMIT = 20

    DEFAULT_CONVERSATION_FIELDS = [
        "id",
        "updated_time",
    ]

    DEFAULT_CONVERSATION_DETAILS_FIELDS = [
        "id",
        "updated_time",
        "link",
    ]

    DEFAULT_MESSAGE_FIELDS = [
        "id",
        "created_time",
        "from",
        "to",
        "message",
        "sticker",
        "attachments",
    ]

    DEFAULT_USER_PROFILE_FIELDS = [
        "id",
        "name",
        "first_name",
        "last_name",
        "email",
        "picture",
    ]

    ALLOWED_MESSAGING_TYPES = {"RESPONSE", "UPDATE", "MESSAGE_TAG"}

    def __init__(self) -> None:
        super().__init__()

        self.page_access_token = self._get_required_env("MESSENGER_PAGE_ACCESS_TOKEN")
        self.page_id = self._get_required_env("MESSENGER_PAGE_ID")
        self.graph_api_version = os.getenv("MESSENGER_GRAPH_API_VERSION", "v25.0").strip()
        self.timeout = self._parse_timeout(os.getenv("MESSENGER_REQUEST_TIMEOUT", "20"))

        self.base_url = f"https://graph.facebook.com/{self.graph_api_version}"
        self.session = self._build_session()

    # =========================
    # Public entrypoint
    # =========================
    def execute(self, arguments: dict[str, Any]) -> Tuple[str, str]:
        """
        Execute requested operation.

        Returns:
            (result_json_or_text, error_text)
        """
        try:
            if self._is_truthy(arguments.get("help")):
                return self._show_help()

            operation = self._required_str(arguments, "operation", allow_empty=False)
            if operation is None:
                return "", "Missing required argument: 'operation'"

            if operation == "send_message":
                return self._op_send_message(arguments)

            if operation == "list_conversations":
                return self._op_list_conversations(arguments)

            if operation == "get_conversation":
                return self._op_get_conversation(arguments)

            if operation == "read_conversation":
                return self._op_read_conversation(arguments)

            if operation == "get_message":
                return self._op_get_message(arguments)

            if operation == "get_user_profile":
                return self._op_get_user_profile(arguments)

            if operation == "health":
                return self._health_check()

            if operation == "help":
                return self._show_help()

            return "", (
                f"Unknown operation: '{operation}'. "
                "Valid operations: send_message, list_conversations, get_conversation, "
                "read_conversation, get_message, get_user_profile, health, help"
            )

        except ValueError as e:
            return "", str(e)
        except Exception as e:
            return "", f"Unexpected error in execute(): {str(e)}"

    # =========================
    # Operation wrappers
    # =========================
    def _op_send_message(self, arguments: Dict[str, Any]) -> Tuple[str, str]:
        recipient_id = self._required_str(arguments, "recipient_id", allow_empty=False)
        message = self._required_str(arguments, "message", allow_empty=False)
        messaging_type = (arguments.get("messaging_type") or "RESPONSE").strip().upper()
        tag = self._optional_str(arguments, "tag")

        return self._send_message(
            recipient_id=recipient_id,
            message=message,
            messaging_type=messaging_type,
            tag=tag,
        )

    def _op_list_conversations(self, arguments: Dict[str, Any]) -> Tuple[str, str]:
        limit, err = self._parse_limit(
            arguments.get("limit"),
            default=self.DEFAULT_LIST_LIMIT,
            max_value=self.MAX_LIMIT,
        )
        if err:
            return "", err

        after = self._optional_str(arguments, "after")
        fields = self._parse_fields(
            arguments.get("fields"),
            default_fields=self.DEFAULT_CONVERSATION_FIELDS,
        )

        return self._list_conversations(limit=limit, after=after, fields=fields)

    def _op_get_conversation(self, arguments: Dict[str, Any]) -> Tuple[str, str]:
        conversation_id = self._required_str(arguments, "conversation_id", allow_empty=False)
        fields = self._parse_fields(
            arguments.get("fields"),
            default_fields=self.DEFAULT_CONVERSATION_DETAILS_FIELDS,
        )

        return self._get_conversation(conversation_id=conversation_id, fields=fields)

    def _op_read_conversation(self, arguments: Dict[str, Any]) -> Tuple[str, str]:
        conversation_id = self._required_str(arguments, "conversation_id", allow_empty=False)

        limit, err = self._parse_limit(
            arguments.get("limit"),
            default=self.DEFAULT_READ_LIMIT,
            max_value=self.MAX_MESSAGE_DETAILS_LIMIT,
        )
        if err:
            return "", err

        after = self._optional_str(arguments, "after")
        include_details = self._parse_bool(arguments.get("include_details"), default=True)

        return self._read_conversation(
            conversation_id=conversation_id,
            limit=limit,
            after=after,
            include_details=include_details,
        )

    def _op_get_message(self, arguments: Dict[str, Any]) -> Tuple[str, str]:
        message_id = self._required_str(arguments, "message_id", allow_empty=False)
        fields = self._parse_fields(
            arguments.get("fields"),
            default_fields=self.DEFAULT_MESSAGE_FIELDS,
        )

        data, error = self._get_message_details(message_id=message_id, fields=fields)
        if error:
            return "", f"Error getting message: {error}"

        # Extract attachments for better display
        attachments = self._extract_attachments(data)
        
        # Build result with flattened message structure
        from_data = data.get("from", {}) or {}
        to_data = (data.get("to", {}) or {}).get("data", [])
        
        result = {
            "message_id": data.get("id", message_id),
            "created_time": data.get("created_time"),
            "from_name": from_data.get("name"),
            "from_id": from_data.get("id"),
            "message": data.get("message"),
            "to": [
                {
                    "name": target.get("name"),
                    "id": target.get("id"),
                }
                for target in to_data
            ],
            "requested_fields": fields,
        }
        
        # Add extracted attachments if present
        if attachments:
            result["attachments"] = attachments
        
        # Add sticker if present
        if data.get("sticker"):
            result["sticker"] = data.get("sticker")
        
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    def _op_get_user_profile(self, arguments: Dict[str, Any]) -> Tuple[str, str]:
        user_id = self._required_str(arguments, "user_id", allow_empty=False)
        fields = self._parse_fields(
            arguments.get("fields"),
            default_fields=self.DEFAULT_USER_PROFILE_FIELDS,
        )

        data, error = self._get_user_profile(user_id=user_id, fields=fields)
        if error:
            return "", f"Error getting user profile: {error}"

        result = {
            "profile": data,
            "requested_fields": fields,
        }
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    # =========================
    # Operations
    # =========================
    def _send_message(
        self,
        recipient_id: str,
        message: str,
        messaging_type: str = "RESPONSE",
        tag: Optional[str] = None,
    ) -> Tuple[str, str]:
        if not recipient_id:
            return "", "Missing required argument: recipient_id"

        if not message:
            return "", "Missing required argument: message"

        if messaging_type not in self.ALLOWED_MESSAGING_TYPES:
            return "", (
                "Invalid messaging_type. Allowed values: "
                "RESPONSE, UPDATE, MESSAGE_TAG"
            )

        if messaging_type == "MESSAGE_TAG" and not tag:
            return "", "Missing required argument: tag when messaging_type=MESSAGE_TAG"

        url = f"{self.base_url}/{self.page_id}/messages"

        payload: Dict[str, Any] = {
            "messaging_type": messaging_type,
            "recipient": {"id": recipient_id},
            "message": {"text": message},
        }

        if tag:
            payload["tag"] = tag

        data, error = self._post(url, json_payload=payload)
        if error:
            return "", f"Error sending message: {error}"

        result = {
            "success": True,
            "recipient_id": data.get("recipient_id"),
            "message_id": data.get("message_id"),
            "request": {
                "page_id": self.page_id,
                "messaging_type": messaging_type,
                "tag": tag,
            },
        }
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    def _list_conversations(
        self,
        limit: int = DEFAULT_LIST_LIMIT,
        after: Optional[str] = None,
        fields: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        url = f"{self.base_url}/{self.page_id}/conversations"

        params: Dict[str, Any] = {
            "platform": "messenger",
            "limit": limit,
        }

        if fields:
            params["fields"] = ",".join(fields)

        if after:
            params["after"] = after

        data, error = self._get(url, params=params)
        if error:
            return "", f"Error listing conversations: {error}"

        conversations = data.get("data", [])
        paging = data.get("paging", {}) if isinstance(data, dict) else {}
        result = {
            "count": len(conversations),
            "conversations": conversations,
            "requested_fields": fields or [],
            "paging": self._normalize_paging(paging),
        }
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    def _get_conversation(
        self,
        conversation_id: str,
        fields: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        if not conversation_id:
            return "", "Missing required argument: conversation_id"

        url = f"{self.base_url}/{conversation_id}"
        params = {}

        if fields:
            params["fields"] = ",".join(fields)

        data, error = self._get(url, params=params)
        if error:
            return "", f"Error getting conversation: {error}"

        result = {
            "conversation": data,
            "requested_fields": fields or [],
        }
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    def _read_conversation(
        self,
        conversation_id: str,
        limit: int = DEFAULT_READ_LIMIT,
        after: Optional[str] = None,
        include_details: bool = True,
    ) -> Tuple[str, str]:
        if not conversation_id:
            return "", "Missing required argument: conversation_id"

        message_refs, paging_info, error = self._get_conversation_message_refs(
            conversation_id=conversation_id,
            limit=limit,
            after=after,
        )
        if error:
            return "", error

        if not message_refs:
            result = {
                "conversation_id": conversation_id,
                "count": 0,
                "messages": [],
                "paging": paging_info,
                "include_details": include_details,
            }
            return json.dumps(result, indent=2, ensure_ascii=False), ""

        if not include_details:
            result = {
                "conversation_id": conversation_id,
                "count": len(message_refs),
                "messages": list(reversed(message_refs)),
                "paging": paging_info,
                "include_details": False,
            }
            return json.dumps(result, indent=2, ensure_ascii=False), ""

        detailed_messages: List[Dict[str, Any]] = []
        detail_errors: List[Dict[str, Any]] = []

        for ref in message_refs:
            message_id = ref.get("id")
            created_time = ref.get("created_time")

            details, detail_error = self._get_message_details(
                message_id,
                fields=self.DEFAULT_MESSAGE_FIELDS,
            )
            if detail_error:
                detail_errors.append(
                    {
                        "message_id": message_id,
                        "created_time": created_time,
                        "error": detail_error,
                    }
                )
                detailed_messages.append(
                    {
                        "message_id": message_id,
                        "created_time": created_time,
                        "from_name": None,
                        "from_id": None,
                        "message": None,
                        "to": [],
                        "detail_error": detail_error,
                    }
                )
                continue

            from_data = details.get("from", {}) or {}
            to_data = (details.get("to", {}) or {}).get("data", [])
            attachments = self._extract_attachments(details)

            message_obj = {
                "message_id": details.get("id", message_id),
                "created_time": details.get("created_time", created_time),
                "from_name": from_data.get("name"),
                "from_id": from_data.get("id"),
                "message": details.get("message"),
                "to": [
                    {
                        "name": target.get("name"),
                        "id": target.get("id"),
                    }
                    for target in to_data
                ],
            }
            
            # Add attachments if present
            if attachments:
                message_obj["attachments"] = attachments
            
            # Add sticker if present
            if details.get("sticker"):
                message_obj["sticker"] = details.get("sticker")
            
            detailed_messages.append(message_obj)

        detailed_messages.reverse()

        result = {
            "conversation_id": conversation_id,
            "count": len(detailed_messages),
            "messages": detailed_messages,
            "paging": paging_info,
            "detail_errors": detail_errors,
            "include_details": True,
        }
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    def _get_conversation_message_refs(
        self,
        conversation_id: str,
        limit: int,
        after: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
        url = f"{self.base_url}/{conversation_id}"
        params: Dict[str, Any] = {
            "fields": f"messages.limit({limit}){{id,created_time}}"
        }
        if after:
            params["after"] = after

        data, error = self._get(url, params=params)
        if error:
            return [], {}, f"Error reading conversation: {error}"

        messages_obj = data.get("messages", {}) if isinstance(data, dict) else {}
        message_refs = messages_obj.get("data", []) if isinstance(messages_obj, dict) else []
        paging = messages_obj.get("paging", {}) if isinstance(messages_obj, dict) else {}

        return message_refs, self._normalize_paging(paging), ""

    def _get_message_details(
        self,
        message_id: Optional[str],
        fields: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        if not message_id:
            return {}, "Missing message ID"

        url = f"{self.base_url}/{message_id}"
        params = {
            "fields": ",".join(fields or self.DEFAULT_MESSAGE_FIELDS)
        }

        data, error = self._get(url, params=params)
        if error:
            return {}, error

        return data, ""

    def _get_user_profile(
        self,
        user_id: str,
        fields: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        if not user_id:
            return {}, "Missing user_id"

        url = f"{self.base_url}/{user_id}"
        params = {
            "fields": ",".join(fields or self.DEFAULT_USER_PROFILE_FIELDS)
        }

        data, error = self._get(url, params=params)
        if error:
            return {}, error

        return data, ""

    def _health_check(self) -> Tuple[str, str]:
        url = f"{self.base_url}/{self.page_id}"
        params = {
            "fields": "id"
        }

        data, error = self._get(url, params=params)
        if error:
            return "", f"Health check failed: {error}"

        result = {
            "success": True,
            "page_id": self.page_id,
            "graph_api_version": self.graph_api_version,
            "timeout": self.timeout,
            "page_response": data,
        }
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    # =========================
    # HTTP helpers
    # =========================
    def _build_session(self) -> requests.Session:
        session = requests.Session()

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        merged_params = self._with_auth(params)

        try:
            response = self.session.get(
                url,
                params=merged_params,
                timeout=self.timeout,
            )
            return self._handle_response(response)

        except requests.exceptions.Timeout:
            return {}, "Request timed out"
        except requests.exceptions.ConnectionError as e:
            return {}, f"Connection error: {str(e)}"
        except requests.exceptions.RequestException as e:
            return {}, f"HTTP request error: {str(e)}"

    def _post(
        self,
        url: str,
        json_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        try:
            response = self.session.post(
                url,
                params={"access_token": self.page_access_token},
                json=json_payload or {},
                timeout=self.timeout,
            )
            return self._handle_response(response)

        except requests.exceptions.Timeout:
            return {}, "Request timed out"
        except requests.exceptions.ConnectionError as e:
            return {}, f"Connection error: {str(e)}"
        except requests.exceptions.RequestException as e:
            return {}, f"HTTP request error: {str(e)}"

    def _handle_response(self, response: requests.Response) -> Tuple[Dict[str, Any], str]:
        content_type = response.headers.get("Content-Type", "")
        is_json = "application/json" in content_type.lower()

        try:
            payload = response.json() if is_json else {"raw_response": response.text}
        except ValueError:
            payload = {"raw_response": response.text}

        if response.ok:
            if isinstance(payload, dict):
                return payload, ""
            return {"result": payload}, ""

        if isinstance(payload, dict) and "error" in payload:
            err = payload.get("error", {}) or {}
            details = {
                "http_status": response.status_code,
                "error_type": err.get("type"),
                "code": err.get("code"),
                "error_subcode": err.get("error_subcode"),
                "message": err.get("message"),
                "fbtrace_id": err.get("fbtrace_id"),
                "raw": payload,
            }
            return {}, json.dumps(details, indent=2, ensure_ascii=False)

        return {}, json.dumps(
            {
                "http_status": response.status_code,
                "raw": payload,
            },
            indent=2,
            ensure_ascii=False,
        )

    def _with_auth(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        out = dict(params or {})
        out["access_token"] = self.page_access_token
        return out

    # =========================
    # Validation / parsing
    # =========================
    def _get_required_env(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"{key} not found in environment. "
                f"Please add: {key}=your_value_here"
            )
        return value.strip()

    def _parse_timeout(self, raw_value: str) -> int:
        try:
            value = int(raw_value)
            return max(value, 5)
        except (TypeError, ValueError):
            return 20

    def _parse_limit(
        self,
        value: Optional[Any],
        default: int,
        max_value: int,
    ) -> Tuple[int, str]:
        if value is None or value == "":
            return default, ""

        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 0, f"Invalid 'limit': {value}. Must be an integer."

        if parsed <= 0:
            return 0, "Invalid 'limit': must be greater than 0"

        if parsed > max_value:
            return max_value, ""

        return parsed, ""

    def _parse_fields(
        self,
        raw_fields: Any,
        default_fields: Optional[List[str]] = None,
    ) -> List[str]:
        if raw_fields is None or raw_fields == "":
            return list(default_fields or [])

        if isinstance(raw_fields, list):
            return [str(f).strip() for f in raw_fields if str(f).strip()]

        if isinstance(raw_fields, str):
            return [part.strip() for part in raw_fields.split(",") if part.strip()]

        raise ValueError("Invalid 'fields': must be a comma-separated string or a list")

    def _parse_bool(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _is_truthy(self, value: Any) -> bool:
        return self._parse_bool(value, default=False)

    def _required_str(
        self,
        arguments: Dict[str, Any],
        key: str,
        allow_empty: bool = False,
    ) -> Optional[str]:
        value = arguments.get(key)
        if value is None:
            return None

        normalized = str(value).strip()
        if not allow_empty and not normalized:
            return None
        return normalized

    def _optional_str(self, arguments: Dict[str, Any], key: str) -> Optional[str]:
        value = arguments.get(key)
        if value is None:
            return None

        normalized = str(value).strip()
        return normalized or None

    def _normalize_paging(self, paging: Any) -> Dict[str, Any]:
        paging = paging if isinstance(paging, dict) else {}
        cursors = paging.get("cursors", {}) if isinstance(paging, dict) else {}

        return {
            "next_cursor": cursors.get("after"),
            "previous_cursor": cursors.get("before"),
            "has_next_page": "next" in paging,
            "has_previous_page": "previous" in paging,
        }

    def _extract_attachments(self, message_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract and format attachments from message data (voice, images, videos, etc.)."""
        attachments_data = message_data.get("attachments", {})
        if not attachments_data or not isinstance(attachments_data, dict):
            return None
        
        attachments = attachments_data.get("data", [])
        if not attachments:
            return None
        
        formatted_attachments = []
        for attachment in attachments:
            # Determine type from mime_type
            mime_type = attachment.get("mime_type", "")
            attachment_type = "file"
            
            if mime_type.startswith("audio"):
                attachment_type = "audio"
            elif mime_type.startswith("image"):
                attachment_type = "image"
            elif mime_type.startswith("video"):
                attachment_type = "video"
            
            formatted = {
                "type": attachment_type,
                "url": attachment.get("file_url"),
                "name": attachment.get("name"),
                "mime_type": mime_type,
                "size": attachment.get("size"),
            }
            
            # Add type-specific info
            if attachment_type == "audio":
                formatted["audio_type"] = "voice_message"
            
            formatted_attachments.append(formatted)
        
        return formatted_attachments if formatted_attachments else None


    # =========================
    # Help
    # =========================
    def _show_help(self) -> Tuple[str, str]:
        help_text = f"""Facebook Messenger Tool

DESCRIPTION:
    Tool for sending messages and reading Facebook Messenger conversations.

CURRENT CONFIG:
    Graph API Version: {self.graph_api_version}
    Page ID: {self.page_id}
    Timeout: {self.timeout}s

REQUIRED ENV:
    MESSENGER_PAGE_ACCESS_TOKEN=your_page_access_token_here
    MESSENGER_PAGE_ID=your_page_id_here

OPTIONAL ENV:
    MESSENGER_GRAPH_API_VERSION={self.graph_api_version}
    MESSENGER_REQUEST_TIMEOUT={self.timeout}

SUPPORTED OPERATIONS:

1) health
   Verify access token / page access and basic API connectivity.

   Example:
   {{
     "operation": "health"
   }}

2) send_message
   Send a text message to a user who already contacted your Page.

   Example:
   {{
     "operation": "send_message",
     "recipient_id": "1234567890",
     "message": "Hello! How can I help you?",
     "messaging_type": "RESPONSE"
   }}

   MESSAGE_TAG example:
   {{
     "operation": "send_message",
     "recipient_id": "1234567890",
     "message": "Order update: your package has shipped.",
     "messaging_type": "MESSAGE_TAG",
     "tag": "POST_PURCHASE_UPDATE"
   }}

3) list_conversations
   List recent Messenger conversations for the page.

   Example:
   {{
     "operation": "list_conversations",
     "limit": 10
   }}

   With fields:
   {{
     "operation": "list_conversations",
     "limit": 10,
     "fields": "id,updated_time,link"
   }}

   With pagination:
   {{
     "operation": "list_conversations",
     "limit": 10,
     "after": "CURSOR_VALUE"
   }}

4) get_conversation
   Get details for one conversation/chat.

   Example:
   {{
     "operation": "get_conversation",
     "conversation_id": "t_xxxxxxxxxxxxx"
   }}

   With explicit fields:
   {{
     "operation": "get_conversation",
     "conversation_id": "t_xxxxxxxxxxxxx",
     "fields": "id,updated_time,link"
   }}

5) read_conversation
   Read messages from a conversation.

   Example:
   {{
     "operation": "read_conversation",
     "conversation_id": "t_xxxxxxxxxxxxx",
     "limit": 20
   }}

   Without fetching full message details:
   {{
     "operation": "read_conversation",
     "conversation_id": "t_xxxxxxxxxxxxx",
     "limit": 20,
     "include_details": false
   }}

   With pagination:
   {{
     "operation": "read_conversation",
     "conversation_id": "t_xxxxxxxxxxxxx",
     "limit": 20,
     "after": "CURSOR_VALUE"
   }}

6) get_message
   Get one message by message_id.

   Example:
   {{
     "operation": "get_message",
     "message_id": "m_xxxxxxxxxxxxx"
   }}

   With explicit fields:
   {{
     "operation": "get_message",
     "message_id": "m_xxxxxxxxxxxxx",
     "fields": "id,created_time,from,to,message"
   }}

7) get_user_profile
   Get basic profile fields for a PSID/user id.

   Example:
   {{
     "operation": "get_user_profile",
     "user_id": "1234567890"
   }}

   With explicit fields:
   {{
     "operation": "get_user_profile",
     "user_id": "1234567890",
     "fields": "id,name"
   }}

8) help
   Show this help text.

IMPORTANT NOTES:
    - recipient_id is usually the user's PSID (Page-Scoped ID)
    - get_user_profile NOW returns first_name, last_name, email, picture by default!
    - list_conversations uses platform=messenger
    - read_conversation first fetches message refs, then optionally message details
    - Meta may restrict detailed data to only the most recent messages
    - current implementation caps detailed message reading at {self.MAX_MESSAGE_DETAILS_LIMIT}
    - fields support depends on your app permissions and API availability
    - Meta messaging windows, tags and platform policies still apply

COMMON ERRORS:
    - invalid/expired page token
    - missing page permissions
    - requesting unsupported fields
    - trying to message a user who never contacted the Page
"""
        return help_text, ""


if __name__ == "__main__":
    tool = MessengerTool()

    def run_case(title: str, payload: dict):
        print("\n" + "=" * 60)
        print(f"CASE: {title}")
        print("- payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        result, error = tool.execute(payload)

        if error:
            print("- ERROR:")
            print(error)
        else:
            print("- RESULT:")
            try:
                parsed = json.loads(result)
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except Exception:
                print(result)

    # =========================
    # BASIC / DEBUG
    # =========================
    run_case(
        "HELP",
        {"operation": "help"}
    )

    run_case(
        "HEALTH CHECK",
        {"operation": "health"}
    )

    # =========================
    # SEND MESSAGE
    # =========================
    run_case(
        "SEND MESSAGE (RESPONSE)",
        {
            "operation": "send_message",
            "recipient_id": "USER_PSID_HERE",
            "message": "Hello from MessengerTool 👋",
            "messaging_type": "RESPONSE"
        }
    )

    run_case(
        "SEND MESSAGE (MESSAGE_TAG)",
        {
            "operation": "send_message",
            "recipient_id": "USER_PSID_HERE",
            "message": "Your order has shipped 📦",
            "messaging_type": "MESSAGE_TAG",
            "tag": "POST_PURCHASE_UPDATE"
        }
    )

    # =========================
    # CONVERSATIONS
    # =========================
    run_case(
        "LIST CONVERSATIONS (default)",
        {
            "operation": "list_conversations"
        }
    )

    run_case(
        "LIST CONVERSATIONS (with fields)",
        {
            "operation": "list_conversations",
            "limit": 5,
            "fields": "id,updated_time"
        }
    )

    # =========================
    # SINGLE CONVERSATION
    # =========================
    run_case(
        "GET CONVERSATION",
        {
            "operation": "get_conversation",
            "conversation_id": "t_CONVERSATION_ID_HERE"
        }
    )

    # =========================
    # READ MESSAGES
    # =========================
    run_case(
        "READ CONVERSATION (with details)",
        {
            "operation": "read_conversation",
            "conversation_id": "t_CONVERSATION_ID_HERE",
            "limit": 5,
            "include_details": True
        }
    )

    run_case(
        "READ CONVERSATION (without details)",
        {
            "operation": "read_conversation",
            "conversation_id": "t_CONVERSATION_ID_HERE",
            "limit": 5,
            "include_details": False
        }
    )

    # =========================
    # MESSAGE
    # =========================
    run_case(
        "GET MESSAGE",
        {
            "operation": "get_message",
            "message_id": "m_MESSAGE_ID_HERE"
        }
    )

    # =========================
    # USER PROFILE
    # =========================
    run_case(
        "GET USER PROFILE",
        {
            "operation": "get_user_profile",
            "user_id": "USER_PSID_HERE"
        }
    )

    print("\n" + "=" * 60)
    print("DONE")
