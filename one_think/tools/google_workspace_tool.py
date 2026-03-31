from one_think.tools import Tool
import os
import json
import base64
from typing import Optional
from dotenv import load_dotenv

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
    name = "google_workspace"
    description = "Manages Google Workspace services: Gmail, Calendar, Tasks."
    
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
    
    def _check_apis_available(self):
        """Check if Google APIs are installed."""
        if not GOOGLE_APIS_AVAILABLE:
            return False, (
                "Google API libraries not installed. Install with:\n"
                "pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )
        return True, ""
    
    def _get_credentials(self):
        """Get or refresh Google credentials."""
        if self.creds and self.creds.valid:
            return self.creds, ""
        
        # Load token if exists
        if os.path.exists(self.token_path):
            try:
                self.creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
            except Exception as e:
                return None, f"Error loading token: {e}"
        
        # Refresh if expired
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
            except Exception as e:
                return None, f"Error refreshing token: {e}"
        
        # New authorization needed
        if not self.creds or not self.creds.valid:
            if not os.path.exists(self.credentials_path):
                return None, (
                    f"Google credentials file not found at: {self.credentials_path}\n"
                    "Please download credentials from Google Cloud Console:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create OAuth 2.0 credentials\n"
                    "3. Save as google_credentials.json in persistent/ directory"
                )
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES
                )
                self.creds = flow.run_local_server(port=0)
                
                # Save token
                os.makedirs(os.path.dirname(self.token_path) or '.', exist_ok=True)
                with open(self.token_path, 'w') as token:
                    token.write(self.creds.to_json())
                    
            except Exception as e:
                return None, f"Error during authorization: {e}"
        
        return self.creds, ""
    
    def _gmail_send(self, to: str, subject: str, body: str):
        """Send an email via Gmail."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            # Create message
            from email.mime.text import MIMEText
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send
            result = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            return f"Email sent successfully. Message ID: {result['id']}", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error sending email: {e}"
    
    def _gmail_list(self, max_results: int = 10, include_body: bool = False):
        """List recent emails."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            results = service.users().messages().list(
                userId='me',
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return "No messages found", ""
            
            email_list = []
            for msg in messages:
                # Get message format based on include_body
                msg_format = 'full' if include_body else 'metadata'
                
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format=msg_format,
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = message['payload']['headers']
                email_info = {
                    'id': msg['id'],
                    'from': next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown'),
                    'subject': next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject'),
                    'date': next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown'),
                    'snippet': message.get('snippet', '')
                }
                
                # Add body if requested
                if include_body:
                    body = self._extract_email_body(message)
                    email_info['body'] = body
                
                email_list.append(email_info)
            
            return json.dumps({'count': len(email_list), 'emails': email_list}, indent=2), ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error listing emails: {e}"
    
    def _extract_email_body(self, message):
        """Extract body from email message."""
        try:
            if 'parts' in message['payload']:
                # Multipart message
                parts = message['payload']['parts']
                body = ''
                for part in parts:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            break
                    elif part['mimeType'] == 'text/html' and not body:
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                return body
            else:
                # Single part message
                if 'data' in message['payload']['body']:
                    return base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
                return ''
        except Exception as e:
            return f"[Error extracting body: {e}]"
    
    def _gmail_get(self, message_id: str):
        """Get full email content by message ID."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            
            email_data = {
                'id': message['id'],
                'thread_id': message.get('threadId'),
                'from': next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown'),
                'to': next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown'),
                'subject': next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject'),
                'date': next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown'),
                'snippet': message.get('snippet', ''),
                'body': self._extract_email_body(message),
                'labels': message.get('labelIds', [])
            }
            
            return json.dumps(email_data, indent=2), ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error getting email: {e}"
    
    def _gmail_search(self, query: str, max_results: int = 10):
        """Search emails by query."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not query:
            return "", "Missing required argument: query"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return f"No messages found for query: '{query}'", ""
            
            email_list = []
            for msg in messages:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = message['payload']['headers']
                email_info = {
                    'id': msg['id'],
                    'from': next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown'),
                    'subject': next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject'),
                    'date': next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown'),
                    'snippet': message.get('snippet', '')
                }
                email_list.append(email_info)
            
            return json.dumps({'count': len(email_list), 'query': query, 'emails': email_list}, indent=2), ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error searching emails: {e}"
    
    def _gmail_mark_read(self, message_id: str):
        """Mark email as read."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            return f"Message {message_id} marked as read", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error marking email as read: {e}"
    
    def _gmail_mark_unread(self, message_id: str):
        """Mark email as unread."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['UNREAD']}
            ).execute()
            
            return f"Message {message_id} marked as unread", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error marking email as unread: {e}"
    
    def _gmail_archive(self, message_id: str):
        """Archive email (remove from inbox)."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            
            return f"Message {message_id} archived successfully", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error archiving email: {e}"
    
    def _gmail_unarchive(self, message_id: str):
        """Unarchive email (add back to inbox)."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['INBOX']}
            ).execute()
            
            return f"Message {message_id} restored to inbox", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error unarchiving email: {e}"
    
    def _gmail_trash(self, message_id: str):
        """Move email to trash."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().trash(
                userId='me',
                id=message_id
            ).execute()
            
            return f"Message {message_id} moved to trash", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error moving email to trash: {e}"
    
    def _gmail_untrash(self, message_id: str):
        """Restore email from trash."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().untrash(
                userId='me',
                id=message_id
            ).execute()
            
            return f"Message {message_id} restored from trash", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error restoring email from trash: {e}"
    
    def _gmail_spam(self, message_id: str):
        """Mark email as spam."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['SPAM'], 'removeLabelIds': ['INBOX']}
            ).execute()
            
            return f"Message {message_id} marked as spam", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error marking email as spam: {e}"
    
    def _gmail_star(self, message_id: str):
        """Add star to email."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['STARRED']}
            ).execute()
            
            return f"Message {message_id} starred", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error starring email: {e}"
    
    def _gmail_unstar(self, message_id: str):
        """Remove star from email."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id:
            return "", "Missing required argument: message_id"
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['STARRED']}
            ).execute()
            
            return f"Star removed from message {message_id}", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error unstarring email: {e}"
    
    def _gmail_add_labels(self, message_id: str, labels: str):
        """Add labels to email."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id or not labels:
            return "", "Missing required arguments: message_id, labels"
        
        # Parse labels (comma-separated or JSON list)
        try:
            import json as json_module
            label_list = json_module.loads(labels)
        except:
            label_list = [l.strip() for l in labels.split(',')]
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': label_list}
            ).execute()
            
            return f"Labels {label_list} added to message {message_id}", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error adding labels: {e}"
    
    def _gmail_remove_labels(self, message_id: str, labels: str):
        """Remove labels from email."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not message_id or not labels:
            return "", "Missing required arguments: message_id, labels"
        
        # Parse labels (comma-separated or JSON list)
        try:
            import json as json_module
            label_list = json_module.loads(labels)
        except:
            label_list = [l.strip() for l in labels.split(',')]
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': label_list}
            ).execute()
            
            return f"Labels {label_list} removed from message {message_id}", ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error removing labels: {e}"
    
    def _gmail_list_labels(self):
        """List all available Gmail labels."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        try:
            service = build('gmail', 'v1', credentials=creds)
            
            results = service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            if not labels:
                return "No labels found", ""
            
            label_list = []
            for label in labels:
                label_info = {
                    'id': label['id'],
                    'name': label['name'],
                    'type': label.get('type', 'user')
                }
                label_list.append(label_info)
            
            return json.dumps({'count': len(label_list), 'labels': label_list}, indent=2), ""
            
        except HttpError as e:
            return "", f"Gmail API error: {e}"
        except Exception as e:
            return "", f"Error listing labels: {e}"
    
    def _calendar_list(self, max_results: int = 10):
        """List upcoming calendar events."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        try:
            from datetime import datetime, timezone
            
            service = build('calendar', 'v3', credentials=creds)
            
            now = datetime.now(timezone.utc).isoformat()
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                return "No upcoming events found", ""
            
            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_info = {
                    'id': event['id'],
                    'summary': event.get('summary', 'No Title'),
                    'start': start,
                    'end': event['end'].get('dateTime', event['end'].get('date'))
                }
                event_list.append(event_info)
            
            return json.dumps({'count': len(event_list), 'events': event_list}, indent=2), ""
            
        except HttpError as e:
            return "", f"Calendar API error: {e}"
        except Exception as e:
            return "", f"Error listing events: {e}"
    
    def _calendar_create(self, summary: str, start_time: str, end_time: str):
        """Create a calendar event."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not summary or not start_time or not end_time:
            return "", "Missing required fields: summary, start_time, end_time"
        
        try:
            service = build('calendar', 'v3', credentials=creds)
            
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC',
                }
            }
            
            result = service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            return f"Event created successfully. ID: {result['id']}", ""
            
        except HttpError as e:
            return "", f"Calendar API error: {e}"
        except Exception as e:
            return "", f"Error creating event: {e}"
    
    def _tasks_list(self, task_list_id: str = '@default', max_results: int = 10):
        """List tasks."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        try:
            service = build('tasks', 'v1', credentials=creds)
            
            results = service.tasks().list(
                tasklist=task_list_id,
                maxResults=max_results
            ).execute()
            
            tasks = results.get('items', [])
            
            if not tasks:
                return "No tasks found", ""
            
            task_list = []
            for task in tasks:
                task_info = {
                    'id': task['id'],
                    'title': task.get('title', 'No Title'),
                    'status': task.get('status', 'needsAction'),
                    'due': task.get('due', 'No due date')
                }
                task_list.append(task_info)
            
            return json.dumps({'count': len(task_list), 'tasks': task_list}, indent=2), ""
            
        except HttpError as e:
            return "", f"Tasks API error: {e}"
        except Exception as e:
            return "", f"Error listing tasks: {e}"
    
    def _tasks_create(self, title: str, task_list_id: str = '@default'):
        """Create a new task."""
        creds, error = self._get_credentials()
        if error:
            return "", error
        
        if not title:
            return "", "Missing required field: title"
        
        try:
            service = build('tasks', 'v1', credentials=creds)
            
            task = {
                'title': title
            }
            
            result = service.tasks().insert(
                tasklist=task_list_id,
                body=task
            ).execute()
            
            return f"Task created successfully. ID: {result['id']}", ""
            
        except HttpError as e:
            return "", f"Tasks API error: {e}"
        except Exception as e:
            return "", f"Error creating task: {e}"
    
    def _show_help(self):
        """Show help information."""
        help_text = """Google Workspace Tool - Gmail, Calendar, Tasks Management

DESCRIPTION:
    Integrates with Google Workspace services (Gmail, Calendar, Tasks).
    Requires Google Cloud credentials and OAuth2 authorization.

OPERATIONS:
    
    GMAIL:
    gmail_send         - Send an email
    gmail_list         - List recent emails (with optional body)
    gmail_get          - Get full email content by message ID
    gmail_search       - Search emails by query
    gmail_mark_read    - Mark email as read
    gmail_mark_unread  - Mark email as unread
    gmail_archive      - Archive email (remove from inbox)
    gmail_unarchive    - Restore email to inbox
    gmail_trash        - Move email to trash
    gmail_untrash      - Restore email from trash
    gmail_spam         - Mark email as spam
    gmail_star         - Add star to email
    gmail_unstar       - Remove star from email
    gmail_add_labels   - Add labels to email
    gmail_remove_labels - Remove labels from email
    gmail_list_labels  - List all available labels
    
    CALENDAR:
    calendar_list      - List upcoming events
    calendar_create    - Create a new event
    
    TASKS:
    tasks_list         - List tasks
    tasks_create       - Create a new task
    
    help               - Show this help message

GMAIL OPERATIONS:

    Send Email:
    {"operation": "gmail_send", "to": "user@example.com", 
     "subject": "Hello", "body": "Email content"}
    
    List Emails (headers only):
    {"operation": "gmail_list", "max_results": 10}
    
    List Emails (with body):
    {"operation": "gmail_list", "max_results": 10, "include_body": true}
    
    Get Full Email:
    {"operation": "gmail_get", "message_id": "18d5f..."}
    
    Search Emails:
    {"operation": "gmail_search", "query": "from:user@example.com", "max_results": 10}
    
    Search Query Examples:
    - "from:user@example.com" - emails from specific sender
    - "subject:invoice" - emails with invoice in subject
    - "is:unread" - unread emails
    - "has:attachment" - emails with attachments
    - "after:2026/03/01" - emails after date
    - "newer_than:7d" - emails from last 7 days
    
    Mark as Read:
    {"operation": "gmail_mark_read", "message_id": "18d5f..."}
    
    Mark as Unread:
    {"operation": "gmail_mark_unread", "message_id": "18d5f..."}
    
    Archive Email:
    {"operation": "gmail_archive", "message_id": "18d5f..."}
    
    Unarchive Email:
    {"operation": "gmail_unarchive", "message_id": "18d5f..."}
    
    Move to Trash:
    {"operation": "gmail_trash", "message_id": "18d5f..."}
    
    Restore from Trash:
    {"operation": "gmail_untrash", "message_id": "18d5f..."}
    
    Mark as Spam:
    {"operation": "gmail_spam", "message_id": "18d5f..."}
    
    Star Email:
    {"operation": "gmail_star", "message_id": "18d5f..."}
    
    Unstar Email:
    {"operation": "gmail_unstar", "message_id": "18d5f..."}
    
    Add Labels:
    {"operation": "gmail_add_labels", "message_id": "18d5f...", 
     "labels": "Label1,Label2"}
    # or with JSON list:
    {"operation": "gmail_add_labels", "message_id": "18d5f...", 
     "labels": "[\"Label1\", \"Label2\"]"}
    
    Remove Labels:
    {"operation": "gmail_remove_labels", "message_id": "18d5f...", 
     "labels": "Label1,Label2"}
    
    List All Labels:
    {"operation": "gmail_list_labels"}

CALENDAR OPERATIONS:

    List Events:
    {"operation": "calendar_list", "max_results": 10}
    
    Create Event:
    {"operation": "calendar_create", 
     "summary": "Meeting", 
     "start_time": "2026-03-31T10:00:00",
     "end_time": "2026-03-31T11:00:00"}

TASKS OPERATIONS:

    List Tasks:
    {"operation": "tasks_list", "max_results": 10}
    
    Create Task:
    {"operation": "tasks_create", "title": "Complete project"}

WORKFLOW EXAMPLES:

    1. Read and archive unread emails:
       - Search: {"operation": "gmail_search", "query": "is:unread"}
       - Get full content: {"operation": "gmail_get", "message_id": "..."}
       - Mark as read: {"operation": "gmail_mark_read", "message_id": "..."}
       - Archive: {"operation": "gmail_archive", "message_id": "..."}
    
    2. Find and process invoices:
       - Search: {"operation": "gmail_search", "query": "subject:invoice has:attachment"}
       - Get details: {"operation": "gmail_get", "message_id": "..."}
       - Star for later: {"operation": "gmail_star", "message_id": "..."}
       - Add label: {"operation": "gmail_add_labels", "message_id": "...", "labels": "Invoices"}
    
    3. Clean up inbox:
       - List labels: {"operation": "gmail_list_labels"}
       - Search old emails: {"operation": "gmail_search", "query": "older_than:1y"}
       - Archive batch: Loop through results with gmail_archive
    
    4. Daily email summary:
       - Search: {"operation": "gmail_search", "query": "newer_than:1d"}
       - List with snippets for overview
       - Star important ones

SETUP:

    1. Install required libraries:
       pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
    
    2. Get Google Cloud credentials:
       - Go to https://console.cloud.google.com/
       - Create OAuth 2.0 Client ID
       - Download JSON file
       - Save as: persistent/google_credentials.json
    
    3. Configure .env:
       GOOGLE_CREDENTIALS_PATH=persistent/google_credentials.json
       GOOGLE_TOKEN_PATH=persistent/google_token.json
    
    4. First run will open browser for authorization
       Token will be saved for future use

SCOPES REQUIRED:
    - gmail.send (send emails)
    - gmail.readonly (read emails)
    - gmail.modify (mark read/unread, archive, star, labels, trash, spam)
    - calendar (manage calendar)
    - tasks (manage tasks)

NOTES:
    - First use requires browser authorization
    - Token is cached in persistent/google_token.json
    - Message IDs from gmail_list or gmail_search can be used with other operations
    - Search uses Gmail search syntax (same as in Gmail web interface)
    - Archive removes INBOX label (email stays in All Mail)
    - Labels can be system labels (INBOX, STARRED, SPAM) or custom user labels
    - Use gmail_list_labels to see all available labels and their IDs
"""
        return help_text, ""
    
    def execute(self, arguments: dict[str, str] = None):
        """Execute the Google Workspace operation."""
        if arguments is None:
            return "", "No arguments provided"
        
        # Check for help first
        if arguments.get("help"):
            return self._show_help()
        
        # Check if APIs are available
        available, error = self._check_apis_available()
        if not available:
            return "", error
        
        operation = arguments.get("operation")
        if not operation:
            return "", "Missing required argument: 'operation'"
        
        # Execute operations
        if operation == "gmail_send":
            to = arguments.get("to")
            subject = arguments.get("subject")
            body = arguments.get("body", "")
            
            if not to or not subject:
                return "", "Missing required arguments for 'gmail_send': to, subject"
            
            return self._gmail_send(to, subject, body)
        
        elif operation == "gmail_list":
            max_results = int(arguments.get("max_results", 10))
            include_body = arguments.get("include_body", False)
            if isinstance(include_body, str):
                include_body = include_body.lower() in ('true', '1', 'yes')
            return self._gmail_list(max_results, include_body)
        
        elif operation == "gmail_get":
            message_id = arguments.get("message_id")
            return self._gmail_get(message_id)
        
        elif operation == "gmail_search":
            query = arguments.get("query")
            max_results = int(arguments.get("max_results", 10))
            return self._gmail_search(query, max_results)
        
        elif operation == "gmail_mark_read":
            message_id = arguments.get("message_id")
            return self._gmail_mark_read(message_id)
        
        elif operation == "gmail_mark_unread":
            message_id = arguments.get("message_id")
            return self._gmail_mark_unread(message_id)
        
        elif operation == "gmail_archive":
            message_id = arguments.get("message_id")
            return self._gmail_archive(message_id)
        
        elif operation == "gmail_unarchive":
            message_id = arguments.get("message_id")
            return self._gmail_unarchive(message_id)
        
        elif operation == "gmail_trash":
            message_id = arguments.get("message_id")
            return self._gmail_trash(message_id)
        
        elif operation == "gmail_untrash":
            message_id = arguments.get("message_id")
            return self._gmail_untrash(message_id)
        
        elif operation == "gmail_spam":
            message_id = arguments.get("message_id")
            return self._gmail_spam(message_id)
        
        elif operation == "gmail_star":
            message_id = arguments.get("message_id")
            return self._gmail_star(message_id)
        
        elif operation == "gmail_unstar":
            message_id = arguments.get("message_id")
            return self._gmail_unstar(message_id)
        
        elif operation == "gmail_add_labels":
            message_id = arguments.get("message_id")
            labels = arguments.get("labels")
            return self._gmail_add_labels(message_id, labels)
        
        elif operation == "gmail_remove_labels":
            message_id = arguments.get("message_id")
            labels = arguments.get("labels")
            return self._gmail_remove_labels(message_id, labels)
        
        elif operation == "gmail_list_labels":
            return self._gmail_list_labels()
        
        elif operation == "calendar_list":
            max_results = int(arguments.get("max_results", 10))
            return self._calendar_list(max_results)
        
        elif operation == "calendar_create":
            summary = arguments.get("summary")
            start_time = arguments.get("start_time")
            end_time = arguments.get("end_time")
            return self._calendar_create(summary, start_time, end_time)
        
        elif operation == "tasks_list":
            max_results = int(arguments.get("max_results", 10))
            task_list_id = arguments.get("task_list_id", "@default")
            return self._tasks_list(task_list_id, max_results)
        
        elif operation == "tasks_create":
            title = arguments.get("body") or arguments.get("title")
            task_list_id = arguments.get("task_list_id", "@default")
            return self._tasks_create(title, task_list_id)
        
        elif operation == "help":
            return self._show_help()
        
        else:
            return "", (
                f"Unknown operation: '{operation}'. "
                "Valid operations: gmail_send, gmail_list, gmail_get, gmail_search, "
                "gmail_mark_read, gmail_mark_unread, gmail_archive, gmail_unarchive, "
                "gmail_trash, gmail_untrash, gmail_spam, gmail_star, gmail_unstar, "
                "gmail_add_labels, gmail_remove_labels, gmail_list_labels, "
                "calendar_list, calendar_create, tasks_list, tasks_create, help"
            )


if __name__ == "__main__":
    # Test the tool
    tool = GoogleWorkspaceTool()
    
    print("=" * 60)
    print("Testing Google Workspace Tool")
    print("=" * 60)
    
    # Show help
    print("\nShowing help...")
    result, error = tool.execute({"operation": "help"})
    if error:
        print(f"Error: {error}")
    else:
        print(result[:500] + "...")
    
    print("\n" + "=" * 60)
    print("Note: Full testing requires Google Cloud credentials")
    print("=" * 60)
