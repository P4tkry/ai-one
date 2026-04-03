"""
Google Workspace Tool - Full JSON migration with Pydantic schemas.
Manages Google Workspace services with structured responses and validation.
"""
import os
import json
from typing import Dict, Any, Optional, Literal, List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from one_think.tools.base import Tool, ToolResponse

load_dotenv()

# Google API imports will be added after installing libraries
try:
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_APIS_AVAILABLE = True
except ImportError:
    GOOGLE_APIS_AVAILABLE = False


class GoogleWorkspaceTool(Tool):
    """Tool for Google Workspace integration with structured responses."""
    
    name = "google_workspace"
    description = "Google Workspace integration (Gmail, Drive, Calendar)"
    version = "2.0.0"
    
    # Pydantic schemas
    class Input(BaseModel):
        """Input parameters for Google Workspace operations."""
        operation: str = Field(description="Operation to perform")
        
        # Gmail parameters
        to: Optional[str] = Field(default=None, description="Email recipient")
        subject: Optional[str] = Field(default=None, description="Email subject")
        body: Optional[str] = Field(default=None, description="Email body")
        query: Optional[str] = Field(default=None, description="Gmail search query")
        message_id: Optional[str] = Field(default=None, description="Gmail message ID")
        max_results: Optional[int] = Field(default=10, description="Maximum number of results")
        
        # Calendar parameters
        calendar_id: Optional[str] = Field(default="primary", description="Calendar ID")
        summary: Optional[str] = Field(default=None, description="Event summary/title")
        description: Optional[str] = Field(default=None, description="Event description")
        location: Optional[str] = Field(default=None, description="Event location")
        start_time: Optional[str] = Field(default=None, description="Start time (ISO format)")
        end_time: Optional[str] = Field(default=None, description="End time (ISO format)")
        time_min: Optional[str] = Field(default=None, description="Minimum time filter (ISO format)")
        time_max: Optional[str] = Field(default=None, description="Maximum time filter (ISO format)")
        timezone: Optional[str] = Field(default="UTC", description="Event timezone")
        attendees: Optional[List[str]] = Field(default=None, description="List of attendee emails")
        
        # Tasks parameters
        tasklist_id: Optional[str] = Field(default=None, description="Task list ID")
        task_id: Optional[str] = Field(default=None, description="Task ID")
        title: Optional[str] = Field(default=None, description="Task title")
        notes: Optional[str] = Field(default=None, description="Task notes/description")
        due: Optional[str] = Field(default=None, description="Task due date (ISO format)")
        show_completed: Optional[bool] = Field(default=False, description="Include completed tasks")
        
        # Common parameters
        help: Optional[bool] = Field(default=False, description="Show help information")
        
    class Output(BaseModel):
        """Output format for Google Workspace operations."""
        service: str = Field(description="Google service used")
        operation: str = Field(description="Operation performed")
        success: bool = Field(description="Whether operation succeeded")
        results: Optional[List[Dict[str, Any]]] = Field(description="Operation results")
        error: Optional[str] = Field(description="Error message if failed")

    # Define scopes for Google APIs
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/tasks'
    ]
    
    def __init__(self):
        super().__init__()
        self.creds = None
        self.credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "persistent/google_credentials.json")
        self.token_path = os.getenv("GOOGLE_TOKEN_PATH", "persistent/google_token.json")
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute Google Workspace operation with JSON response."""
        
        # Check for help request first
        if params.get("help"):
            return self._create_success_response(
                result={"help": self.get_help()},
                request_id=request_id
            )
        
        # Check if APIs are available
        if not GOOGLE_APIS_AVAILABLE:
            return self._create_error_response(
                "DependencyError",
                "Google API libraries not installed. Install with: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client",
                request_id=request_id
            )
        
        # Validate operation
        operation = params.get("operation")
        if not operation:
            return self._create_error_response(
                "ValidationError",
                "Missing required parameter: 'operation'",
                request_id=request_id
            )
        
        # Route to operation handlers
        if operation == "authenticate":
            return self._authenticate(params, request_id)
        elif operation == "gmail_send":
            return self._gmail_send(params, request_id)
        elif operation == "gmail_list":
            return self._gmail_list(params, request_id)
        elif operation == "gmail_read":
            return self._gmail_read(params, request_id)
        elif operation == "calendar_list":
            return self._calendar_list(params, request_id)
        elif operation == "calendar_create":
            return self._calendar_create(params, request_id)
        elif operation == "tasks_list":
            return self._tasks_list(params, request_id)
        elif operation == "tasks_create":
            return self._tasks_create(params, request_id)
        elif operation == "tasks_complete":
            return self._tasks_complete(params, request_id)
        elif operation == "status":
            return self._check_status(request_id)
        else:
            return self._create_error_response(
                "OperationError",
                f"Unknown operation: '{operation}'. Valid operations: authenticate, gmail_send, gmail_list, gmail_read, calendar_list, calendar_create, tasks_list, tasks_create, tasks_complete, status",
                request_id=request_id
            )
    
    def _authenticate(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Authenticate with Google APIs."""
        try:
            # Check if credentials exist
            if not os.path.exists(self.credentials_path):
                return self._create_error_response(
                    "AuthError",
                    f"Google credentials file not found: {self.credentials_path}. Please download OAuth 2.0 client credentials from Google Cloud Console.",
                    request_id=request_id
                )
            
            creds = None
            # Load existing token if available
            if os.path.exists(self.token_path):
                try:
                    creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
                except Exception as e:
                    # Token file corrupted, will regenerate
                    pass
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception:
                        # Refresh failed, need new auth
                        creds = None
                
                if not creds:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES
                    )
                    # Run local server for authentication
                    creds = flow.run_local_server(port=0)
                
                # Save credentials for the next run
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            self.creds = creds
            
            return self._create_success_response(
                result={
                    "authenticated": True,
                    "credentials_path": self.credentials_path,
                    "token_path": self.token_path,
                    "scopes": self.SCOPES,
                    "token_valid": creds.valid,
                    "message": "Successfully authenticated with Google Workspace"
                },
                request_id=request_id
            )
            
        except Exception as e:
            return self._create_error_response(
                "AuthError",
                f"Authentication error: {e}",
                request_id=request_id
            )
    
    def _gmail_send(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Send Gmail message."""
        try:
            # Check authentication
            if not self._ensure_authenticated():
                return self._create_error_response(
                    "AuthError", 
                    "Not authenticated. Please run authenticate operation first.",
                    request_id=request_id
                )
            
            # Validate required parameters
            to_email = params.get("to")
            subject = params.get("subject")
            body = params.get("body", "")
            
            if not to_email:
                return self._create_error_response(
                    "ValidationError",
                    "Missing required parameter: 'to'",
                    request_id=request_id
                )
            
            if not subject:
                return self._create_error_response(
                    "ValidationError",
                    "Missing required parameter: 'subject'",
                    request_id=request_id
                )
            
            # Build Gmail service
            service = build('gmail', 'v1', credentials=self.creds)
            
            # Create email message
            import email.mime.text
            import base64
            
            message = email.mime.text.MIMEText(body)
            message['to'] = to_email
            message['subject'] = subject
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send email
            send_result = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            return self._create_success_response(
                result={
                    "message_id": send_result.get('id'),
                    "thread_id": send_result.get('threadId'),
                    "to": to_email,
                    "subject": subject,
                    "status": "sent",
                    "message": f"Email sent successfully to {to_email}"
                },
                request_id=request_id
            )
            
        except HttpError as error:
            return self._create_error_response(
                "ToolExecutionError",
                f"Gmail API error: {error}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                "ToolExecutionError",
                f"Gmail send error: {e}",
                request_id=request_id
            )
    
    def _gmail_list(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """List Gmail messages."""
        try:
            # Check authentication
            if not self._ensure_authenticated():
                return self._create_error_response(
                "ToolExecutionError",
                "Not authenticated. Please run authenticate operation first.",
                request_id=request_id
                )
            
            # Build Gmail service
            service = build('gmail', 'v1', credentials=self.creds)
            
            # Get parameters
            query = params.get("query", "")
            max_results = params.get("max_results", 10)
            
            # List messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            # Get detailed info for each message
            email_list = []
            for msg in messages[:max_results]:  # Limit to prevent too many API calls
                try:
                    msg_detail = service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='metadata',
                        metadataHeaders=['From', 'To', 'Subject', 'Date']
                    ).execute()
                    
                    headers = msg_detail.get('payload', {}).get('headers', [])
                    header_dict = {h['name']: h['value'] for h in headers}
                    
                    email_info = {
                        "id": msg['id'],
                        "thread_id": msg['threadId'],
                        "from": header_dict.get('From', ''),
                        "to": header_dict.get('To', ''),
                        "subject": header_dict.get('Subject', ''),
                        "date": header_dict.get('Date', ''),
                        "labels": msg_detail.get('labelIds', [])
                    }
                    email_list.append(email_info)
                    
                except Exception as e:
                    # Skip this message if error getting details
                    continue
            
            return self._create_success_response(
                result={
                    "messages": email_list,
                    "total_found": len(messages),
                    "returned": len(email_list),
                    "query": query,
                    "message": f"Found {len(email_list)} emails"
                },
                request_id=request_id
            )
            
        except HttpError as error:
            return self._create_error_response(
                "ToolExecutionError",
                f"Gmail API error: {error}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                "ToolExecutionError",
                f"Gmail list error: {e}",
                request_id=request_id
            )
    
    def _gmail_read(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Read specific Gmail message content."""
        try:
            # Check authentication
            if not self._ensure_authenticated():
                return self._create_error_response(
                "ToolExecutionError",
                "Not authenticated. Please run authenticate operation first.",
                request_id=request_id
                )
            
            # Validate required parameters
            message_id = params.get("message_id")
            if not message_id:
                return self._create_error_response(
                "ToolExecutionError",
                "Missing required parameter: 'message_id'",
                request_id=request_id
                )
            
            # Build Gmail service
            service = build('gmail', 'v1', credentials=self.creds)
            
            # Get full message
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = message.get('payload', {}).get('headers', [])
            header_dict = {h['name']: h['value'] for h in headers}
            
            # Extract body content
            def extract_body_content(payload):
                """Extract text content from message payload."""
                body_content = ""
                
                if payload.get('mimeType') == 'text/plain':
                    body_data = payload.get('body', {}).get('data', '')
                    if body_data:
                        import base64
                        body_content = base64.urlsafe_b64decode(body_data).decode('utf-8')
                elif payload.get('mimeType') == 'text/html':
                    body_data = payload.get('body', {}).get('data', '')
                    if body_data:
                        import base64
                        body_content = base64.urlsafe_b64decode(body_data).decode('utf-8')
                elif payload.get('parts'):
                    # Multipart message
                    for part in payload['parts']:
                        if part.get('mimeType') == 'text/plain':
                            part_data = part.get('body', {}).get('data', '')
                            if part_data:
                                import base64
                                body_content += base64.urlsafe_b64decode(part_data).decode('utf-8')
                                break
                
                return body_content
            
            body = extract_body_content(message.get('payload', {}))
            
            return self._create_success_response(
                result={
                    "message_id": message_id,
                    "thread_id": message.get('threadId'),
                    "from": header_dict.get('From', ''),
                    "to": header_dict.get('To', ''),
                    "subject": header_dict.get('Subject', ''),
                    "date": header_dict.get('Date', ''),
                    "body": body,
                    "snippet": message.get('snippet', ''),
                    "labels": message.get('labelIds', []),
                    "size_estimate": message.get('sizeEstimate', 0),
                    "message": "Message content retrieved successfully"
                },
                request_id=request_id
            )
            
        except HttpError as error:
            return self._create_error_response(
                "ToolExecutionError",
                f"Gmail API error: {error}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                "ToolExecutionError",
                f"Gmail read error: {e}",
                request_id=request_id
            )
    
    def _calendar_list(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """List Calendar events."""
        try:
            # Check authentication
            if not self._ensure_authenticated():
                return self._create_error_response(
                "ToolExecutionError",
                "Not authenticated. Please run authenticate operation first.",
                request_id=request_id
                )
            
            # Build Calendar service
            service = build('calendar', 'v3', credentials=self.creds)
            
            # Get parameters
            calendar_id = params.get("calendar_id", "primary")
            max_results = params.get("max_results", 10)
            time_min = params.get("time_min")  # ISO format
            time_max = params.get("time_max")  # ISO format
            
            # List events
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Format events
            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                event_info = {
                    "id": event.get('id'),
                    "summary": event.get('summary', ''),
                    "description": event.get('description', ''),
                    "start": start,
                    "end": end,
                    "location": event.get('location', ''),
                    "attendees": [
                        {"email": att.get('email'), "status": att.get('responseStatus')} 
                        for att in event.get('attendees', [])
                    ],
                    "creator": event.get('creator', {}).get('email', ''),
                    "html_link": event.get('htmlLink', '')
                }
                event_list.append(event_info)
            
            return self._create_success_response(
                result={
                    "events": event_list,
                    "total_found": len(events),
                    "calendar_id": calendar_id,
                    "message": f"Found {len(event_list)} calendar events"
                },
                request_id=request_id
            )
            
        except HttpError as error:
            return self._create_error_response(
                "ToolExecutionError",
                f"Calendar API error: {error}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                "ToolExecutionError",
                f"Calendar list error: {e}",
                request_id=request_id
            )
    
    def _calendar_create(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Create Calendar event."""
        try:
            # Check authentication
            if not self._ensure_authenticated():
                return self._create_error_response(
                "ToolExecutionError",
                "Not authenticated. Please run authenticate operation first.",
                request_id=request_id
                )
            
            # Validate required parameters
            summary = params.get("summary")
            start_time = params.get("start_time")
            end_time = params.get("end_time")
            
            if not summary:
                return self._create_error_response(
                "ToolExecutionError",
                "Missing required parameter: 'summary'",
                request_id=request_id
                )
            
            if not start_time:
                return self._create_error_response(
                "ToolExecutionError",
                "Missing required parameter: 'start_time' (ISO format)",
                request_id=request_id
                )
            
            if not end_time:
                return self._create_error_response(
                "ToolExecutionError",
                "Missing required parameter: 'end_time' (ISO format)",
                request_id=request_id
                )
            
            # Build Calendar service
            service = build('calendar', 'v3', credentials=self.creds)
            
            # Optional parameters
            calendar_id = params.get("calendar_id", "primary")
            description = params.get("description", "")
            location = params.get("location", "")
            attendees_list = params.get("attendees", [])  # List of email addresses
            
            # Create event object
            event = {
                'summary': summary,
                'description': description,
                'location': location,
                'start': {
                    'dateTime': start_time,
                    'timeZone': params.get("timezone", "UTC"),
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': params.get("timezone", "UTC"),
                },
                'attendees': [{'email': email} for email in attendees_list] if attendees_list else [],
                'reminders': {
                    'useDefault': True,
                },
            }
            
            # Create event
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event,
                sendUpdates='all' if attendees_list else 'none'
            ).execute()
            
            return self._create_success_response(
                result={
                    "event_id": created_event.get('id'),
                    "summary": created_event.get('summary'),
                    "start": created_event['start'].get('dateTime'),
                    "end": created_event['end'].get('dateTime'),
                    "html_link": created_event.get('htmlLink'),
                    "calendar_id": calendar_id,
                    "attendees_count": len(attendees_list),
                    "status": created_event.get('status'),
                    "message": f"Event '{summary}' created successfully"
                },
                request_id=request_id
            )
            
        except HttpError as error:
            return self._create_error_response(
                "ToolExecutionError",
                f"Calendar API error: {error}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                "ToolExecutionError",
                f"Calendar create error: {e}",
                request_id=request_id
            )
    
    def _tasks_list(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """List Google Tasks."""
        try:
            # Check authentication
            if not self._ensure_authenticated():
                return self._create_error_response(
                "ToolExecutionError",
                "Not authenticated. Please run authenticate operation first.",
                request_id=request_id
                )
            
            # Build Tasks service
            service = build('tasks', 'v1', credentials=self.creds)
            
            # Get task lists first
            lists_result = service.tasklists().list().execute()
            task_lists = lists_result.get('items', [])
            
            if not task_lists:
                return self._create_success_response(
                    result={
                        "task_lists": [],
                        "tasks": [],
                        "total_tasks": 0,
                        "message": "No task lists found"
                    },
                    request_id=request_id
                )
            
            # Get parameters
            tasklist_id = params.get("tasklist_id")
            if not tasklist_id:
                tasklist_id = task_lists[0]['id']  # Use first list as default
            
            max_results = params.get("max_results", 20)
            show_completed = params.get("show_completed", False)
            
            # List tasks
            tasks_result = service.tasks().list(
                tasklist=tasklist_id,
                maxResults=max_results,
                showCompleted=show_completed,
                showHidden=False
            ).execute()
            
            tasks = tasks_result.get('items', [])
            
            # Format tasks
            task_list = []
            for task in tasks:
                task_info = {
                    "id": task.get('id'),
                    "title": task.get('title', ''),
                    "notes": task.get('notes', ''),
                    "status": task.get('status', ''),
                    "due": task.get('due', ''),
                    "completed": task.get('completed', ''),
                    "updated": task.get('updated', ''),
                    "parent": task.get('parent', ''),  # For subtasks
                    "position": task.get('position', ''),
                    "self_link": task.get('selfLink', '')
                }
                task_list.append(task_info)
            
            # Format task lists info
            lists_info = [
                {
                    "id": tl.get('id'),
                    "title": tl.get('title'),
                    "updated": tl.get('updated'),
                    "self_link": tl.get('selfLink')
                }
                for tl in task_lists
            ]
            
            return self._create_success_response(
                result={
                    "task_lists": lists_info,
                    "current_list_id": tasklist_id,
                    "tasks": task_list,
                    "total_tasks": len(task_list),
                    "show_completed": show_completed,
                    "message": f"Found {len(task_list)} tasks in list"
                },
                request_id=request_id
            )
            
        except HttpError as error:
            return self._create_error_response(
                "ToolExecutionError",
                f"Tasks API error: {error}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                "ToolExecutionError",
                f"Tasks list error: {e}",
                request_id=request_id
            )
    
    def _tasks_create(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Create a new Google Task."""
        try:
            # Check authentication
            if not self._ensure_authenticated():
                return self._create_error_response(
                "ToolExecutionError",
                "Not authenticated. Please run authenticate operation first.",
                request_id=request_id
                )
            
            # Validate required parameters
            title = params.get("title")
            if not title:
                return self._create_error_response(
                "ToolExecutionError",
                "Missing required parameter: 'title'",
                request_id=request_id
                )
            
            # Build Tasks service
            service = build('tasks', 'v1', credentials=self.creds)
            
            # Get task list ID
            tasklist_id = params.get("tasklist_id")
            if not tasklist_id:
                # Get default task list
                lists_result = service.tasklists().list().execute()
                task_lists = lists_result.get('items', [])
                if not task_lists:
                    return self._create_error_response(
                "ToolExecutionError",
                "No task lists found. Create a task list first.",
                request_id=request_id
                    )
                tasklist_id = task_lists[0]['id']
            
            # Optional parameters
            notes = params.get("notes", "")
            due = params.get("due")  # ISO format date
            
            # Create task object
            task = {
                'title': title,
                'notes': notes
            }
            
            if due:
                task['due'] = due
            
            # Create task
            created_task = service.tasks().insert(
                tasklist=tasklist_id,
                body=task
            ).execute()
            
            return self._create_success_response(
                result={
                    "task_id": created_task.get('id'),
                    "title": created_task.get('title'),
                    "notes": created_task.get('notes', ''),
                    "due": created_task.get('due', ''),
                    "status": created_task.get('status'),
                    "tasklist_id": tasklist_id,
                    "self_link": created_task.get('selfLink', ''),
                    "message": f"Task '{title}' created successfully"
                },
                request_id=request_id
            )
            
        except HttpError as error:
            return self._create_error_response(
                "ToolExecutionError",
                f"Tasks API error: {error}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                "ToolExecutionError",
                f"Tasks create error: {e}",
                request_id=request_id
            )
    
    def _tasks_complete(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Mark a Google Task as completed."""
        try:
            # Check authentication
            if not self._ensure_authenticated():
                return self._create_error_response(
                "ToolExecutionError",
                "Not authenticated. Please run authenticate operation first.",
                request_id=request_id
                )
            
            # Validate required parameters
            task_id = params.get("task_id")
            if not task_id:
                return self._create_error_response(
                "ToolExecutionError",
                "Missing required parameter: 'task_id'",
                request_id=request_id
                )
            
            tasklist_id = params.get("tasklist_id")
            if not tasklist_id:
                return self._create_error_response(
                "ToolExecutionError",
                "Missing required parameter: 'tasklist_id'",
                request_id=request_id
                )
            
            # Build Tasks service
            service = build('tasks', 'v1', credentials=self.creds)
            
            # Get current task
            task = service.tasks().get(
                tasklist=tasklist_id,
                task=task_id
            ).execute()
            
            # Update task status
            task['status'] = 'completed'
            
            # Update task
            updated_task = service.tasks().update(
                tasklist=tasklist_id,
                task=task_id,
                body=task
            ).execute()
            
            return self._create_success_response(
                result={
                    "task_id": updated_task.get('id'),
                    "title": updated_task.get('title'),
                    "status": updated_task.get('status'),
                    "completed": updated_task.get('completed', ''),
                    "updated": updated_task.get('updated', ''),
                    "message": f"Task '{updated_task.get('title')}' marked as completed"
                },
                request_id=request_id
            )
            
        except HttpError as error:
            return self._create_error_response(
                "ToolExecutionError",
                f"Tasks API error: {error}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                "ToolExecutionError",
                f"Tasks complete error: {e}",
                request_id=request_id
            )
    
    def _ensure_authenticated(self) -> bool:
        """Ensure user is authenticated with Google APIs."""
        if not self.creds:
            # Try to load existing credentials
            if os.path.exists(self.token_path):
                try:
                    self.creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
                except Exception:
                    return False
            else:
                return False
        
        # Check if credentials are valid
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                    # Save refreshed token
                    with open(self.token_path, 'w') as token:
                        token.write(self.creds.to_json())
                except Exception:
                    return False
            else:
                return False
        
        return True
    
    def _check_status(self, request_id: Optional[str]) -> ToolResponse:
        """Check Google Workspace connection status."""
        is_authenticated = self._ensure_authenticated()
        
        return self._create_success_response(
            result={
                "apis_available": GOOGLE_APIS_AVAILABLE,
                "credentials_exists": os.path.exists(self.credentials_path),
                "token_exists": os.path.exists(self.token_path),
                "authenticated": is_authenticated,
                "token_valid": self.creds.valid if self.creds else False,
                "status": "fully_implemented",
                "scopes": self.SCOPES,
                "message": "Google Workspace tool is fully functional" if is_authenticated else "Authentication required"
            },
            request_id=request_id
        )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return """Google Workspace Tool

DESCRIPTION:
    Full integration with Google Workspace services: Gmail, Calendar, Tasks.
    Supports sending emails, managing calendar events, and working with tasks.

OPERATIONS:
    authenticate     - Authenticate with Google APIs (required first step)
    gmail_send      - Send Gmail message
    gmail_list      - List Gmail messages
    gmail_read      - Read full Gmail message content
    calendar_list   - List Calendar events
    calendar_create - Create Calendar event
    tasks_list      - List Google Tasks
    tasks_create    - Create Google Task
    tasks_complete  - Mark Google Task as completed
    status          - Check connection status

GMAIL OPERATIONS:
    gmail_send:
        Required: to, subject
        Optional: body
        Example: {"operation": "gmail_send", "to": "user@example.com", "subject": "Test", "body": "Hello!"}
    
    gmail_list:
        Optional: query, max_results (default: 10)
        Example: {"operation": "gmail_list", "query": "from:important@company.com", "max_results": 5}

    gmail_read:
        Required: message_id
        Example: {"operation": "gmail_read", "message_id": "18fabc123def4567"}
        Returns: full headers + decoded body (when available)

CALENDAR OPERATIONS:
    calendar_list:
        Optional: calendar_id (default: "primary"), max_results, time_min, time_max
        Example: {"operation": "calendar_list", "max_results": 5}
    
    calendar_create:
        Required: summary, start_time, end_time (ISO format)
        Optional: description, location, attendees, timezone, calendar_id
        Example: {"operation": "calendar_create", "summary": "Meeting", "start_time": "2026-04-03T10:00:00", "end_time": "2026-04-03T11:00:00"}

TASKS OPERATIONS:
    tasks_list:
        Optional: tasklist_id, max_results (default: 20), show_completed (default: false)
        Example: {"operation": "tasks_list", "show_completed": true}

AUTHENTICATION:
    First run: {"operation": "authenticate"}
    This will open browser for OAuth consent and save credentials.

CONFIGURATION:
    Set in .env file:
        GOOGLE_CREDENTIALS_PATH=persistent/google_credentials.json
        GOOGLE_TOKEN_PATH=persistent/google_token.json

    Setup steps:
        1. Go to Google Cloud Console
        2. Enable Gmail, Calendar, Tasks APIs
        3. Create OAuth 2.0 credentials
        4. Download as google_credentials.json
        5. Run authenticate operation

RESPONSE FORMAT:
    Success:
        {
            "status": "success",
            "result": {
                // Operation-specific data
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
    - Full OAuth 2.0 implementation with token refresh
    - Supports all major Google Workspace operations
    - Automatic credential management
    - Rich error handling and validation
"""
