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
    - read_conversation
    - help

    Required environment variables:
    - MESSENGER_PAGE_ACCESS_TOKEN
    - MESSENGER_PAGE_ID

    Optional environment variables:
    - MESSENGER_GRAPH_API_VERSION (default: v25.0)
    - MESSENGER_REQUEST_TIMEOUT (default: 20)
    """

    name = "messenger"
    description = (
        "Send and receive messages via Facebook Messenger. "
        "Operations: send_message, list_conversations, read_conversation, help."
    )
    arguments = {
        "operation": (
            "Operation to perform: send_message, list_conversations, "
            "read_conversation, help"
        ),
        "recipient_id": "Recipient PSID (Page-Scoped ID) for send_message",
        "message": "Message text to send",
        "conversation_id": "Conversation ID for read_conversation",
        "limit": "Number of items to retrieve",
        "after": "Pagination cursor for list_conversations or read_conversation",
        "messaging_type": (
            "Messaging type for send_message: RESPONSE, UPDATE, MESSAGE_TAG "
            "(default: RESPONSE)"
        ),
        "tag": "Required when messaging_type=MESSAGE_TAG",
        "help": "Show help information (optional, boolean)",
    }

    DEFAULT_LIST_LIMIT = 10
    DEFAULT_READ_LIMIT = 20
    MAX_LIMIT = 100

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
    def execute(self, arguments: dict[str, str]) -> Tuple[str, str]:
        """
        Execute the requested operation.

        Returns:
            Tuple[str, str] -> (result, error)
        """
        try:
            if self._is_truthy(arguments.get("help")):
                return self._show_help()

            operation = (arguments.get("operation") or "").strip()

            if not operation:
                return "", "Missing required argument: 'operation'"

            if operation == "send_message":
                recipient_id = (arguments.get("recipient_id") or "").strip()
                message = (arguments.get("message") or "").strip()
                messaging_type = (arguments.get("messaging_type") or "RESPONSE").strip().upper()
                tag = (arguments.get("tag") or "").strip() or None

                return self._send_message(
                    recipient_id=recipient_id,
                    message=message,
                    messaging_type=messaging_type,
                    tag=tag,
                )

            if operation == "list_conversations":
                limit, err = self._parse_limit(
                    arguments.get("limit"),
                    default=self.DEFAULT_LIST_LIMIT,
                    max_value=self.MAX_LIMIT,
                )
                if err:
                    return "", err

                after = (arguments.get("after") or "").strip() or None
                return self._list_conversations(limit=limit, after=after)

            if operation == "read_conversation":
                conversation_id = (arguments.get("conversation_id") or "").strip()
                limit, err = self._parse_limit(
                    arguments.get("limit"),
                    default=self.DEFAULT_READ_LIMIT,
                    max_value=20,  # message details only for 20 most recent
                )
                if err:
                    return "", err

                after = (arguments.get("after") or "").strip() or None
                return self._read_conversation(
                    conversation_id=conversation_id,
                    limit=limit,
                    after=after,
                )

            if operation == "help":
                return self._show_help()

            return "", (
                f"Unknown operation: '{operation}'. "
                "Valid operations: send_message, list_conversations, "
                "read_conversation, help"
            )

        except Exception as e:
            return "", f"Unexpected error in execute(): {str(e)}"

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
        """
        Send a text message to a user by PSID.
        Current Messenger docs describe sending to /PAGE-ID/messages with
        recipient and messaging_type.
        """
        if not recipient_id:
            return "", "Missing required argument: recipient_id"

        if not message:
            return "", "Missing required argument: message"

        allowed_messaging_types = {"RESPONSE", "UPDATE", "MESSAGE_TAG"}
        if messaging_type not in allowed_messaging_types:
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
    ) -> Tuple[str, str]:
        """
        Get conversation list for the page.

        Conversations API requires:
        GET /PAGE-ID/conversations?platform=messenger
        """
        url = f"{self.base_url}/{self.page_id}/conversations"

        params: Dict[str, Any] = {
            "platform": "messenger",
            "limit": limit,
        }
        if after:
            params["after"] = after

        data, error = self._get(url, params=params)
        if error:
            return "", f"Error listing conversations: {error}"

        conversations = data.get("data", [])
        paging = data.get("paging", {}) if isinstance(data, dict) else {}
        cursors = paging.get("cursors", {}) if isinstance(paging, dict) else {}

        normalized = []
        for conv in conversations:
            normalized.append(
                {
                    "conversation_id": conv.get("id"),
                    "updated_time": conv.get("updated_time"),
                }
            )

        result = {
            "count": len(normalized),
            "conversations": normalized,
            "paging": {
                "next_cursor": cursors.get("after"),
                "previous_cursor": cursors.get("before"),
                "has_next_page": "next" in paging if isinstance(paging, dict) else False,
            },
        }
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    def _read_conversation(
        self,
        conversation_id: str,
        limit: int = DEFAULT_READ_LIMIT,
        after: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Read messages from a conversation.

        Step 1:
            GET /CONVERSATION-ID?fields=messages.limit(N){id,created_time}

        Step 2:
            For each message ID, GET /MESSAGE-ID?fields=id,created_time,from,to,message

        Meta notes that detailed info can only be queried for the 20 most recent messages.
        """
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
            }
            return json.dumps(result, indent=2, ensure_ascii=False), ""

        detailed_messages: List[Dict[str, Any]] = []
        detail_errors: List[Dict[str, Any]] = []

        # Conversation API returns most recent first.
        # We reverse later so output is oldest-first.
        for ref in message_refs:
            message_id = ref.get("id")
            created_time = ref.get("created_time")

            details, detail_error = self._get_message_details(message_id)
            if detail_error:
                detail_errors.append(
                    {
                        "message_id": message_id,
                        "created_time": created_time,
                        "error": detail_error,
                    }
                )
                # Still keep basic info so caller sees something.
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

            detailed_messages.append(
                {
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
            )

        detailed_messages.reverse()

        result = {
            "conversation_id": conversation_id,
            "count": len(detailed_messages),
            "messages": detailed_messages,
            "paging": paging_info,
            "detail_errors": detail_errors,
        }
        return json.dumps(result, indent=2, ensure_ascii=False), ""

    # =========================
    # Conversation readers
    # =========================
    def _get_conversation_message_refs(
        self,
        conversation_id: str,
        limit: int,
        after: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
        """
        Get message IDs and created_time from a conversation.
        """
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
        cursors = paging.get("cursors", {}) if isinstance(paging, dict) else {}

        paging_info = {
            "next_cursor": cursors.get("after"),
            "previous_cursor": cursors.get("before"),
            "has_next_page": "next" in paging if isinstance(paging, dict) else False,
        }

        return message_refs, paging_info, ""

    def _get_message_details(self, message_id: Optional[str]) -> Tuple[Dict[str, Any], str]:
        """
        Get detailed fields for a single message.
        """
        if not message_id:
            return {}, "Missing message ID"

        url = f"{self.base_url}/{message_id}"
        params = {
            "fields": "id,created_time,from,to,message"
        }

        data, error = self._get(url, params=params)
        if error:
            return {}, error

        return data, ""

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
        value: Optional[str],
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

    def _is_truthy(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

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
    MESSENGER_GRAPH_API_VERSION={self.graph_api_version}

OPERATIONS:

1) send_message
   Send a text message to a user who already contacted your Page.

   Example:
   {{
     "operation": "send_message",
     "recipient_id": "1234567890",
     "message": "Hello! How can I help you?",
     "messaging_type": "RESPONSE"
   }}

   Optional MESSAGE_TAG example:
   {{
     "operation": "send_message",
     "recipient_id": "1234567890",
     "message": "Order update: your package has shipped.",
     "messaging_type": "MESSAGE_TAG",
     "tag": "POST_PURCHASE_UPDATE"
   }}

2) list_conversations
   List recent conversations.

   Example:
   {{
     "operation": "list_conversations",
     "limit": 10
   }}

   With pagination:
   {{
     "operation": "list_conversations",
     "limit": 10,
     "after": "CURSOR_VALUE"
   }}

3) read_conversation
   Read messages from a conversation.

   Example:
   {{
     "operation": "read_conversation",
     "conversation_id": "t_xxxxxxxxxxxxx",
     "limit": 20
   }}

   With pagination:
   {{
     "operation": "read_conversation",
     "conversation_id": "t_xxxxxxxxxxxxx",
     "limit": 20,
     "after": "CURSOR_VALUE"
   }}

NOTES:
    - recipient_id is the user's PSID (Page-Scoped ID)
    - list_conversations requires platform=messenger
    - read_conversation fetches message IDs first, then message details
    - detailed data may only be available for the 20 most recent messages
    - Meta messaging window and policy restrictions still apply
"""
        return help_text, ""


if __name__ == "__main__":
    tool = MessengerTool()

    result, error = tool.execute({"operation": "help"})

    if error:
        print("ERROR:")
        print(error)
    else:
        print(result)