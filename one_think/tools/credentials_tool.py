"""
Credentials Tool - Full JSON migration
Manages encrypted credentials in SQLite with structured responses
"""
import sqlite3
import os
import base64
import json
from typing import Any, Dict, Optional, List
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

from one_think.tools.base import Tool, ToolResponse

load_dotenv()


class CredentialsTool(Tool):
    """Tool for managing encrypted credentials in SQLite."""
    
    name = "credentials"
    description = "Manages encrypted credentials stored in SQLite database."
    
    def __init__(self):
        super().__init__()
        self.db_path: Optional[str] = None
        self.cipher: Optional[Fernet] = None
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute credentials operation with JSON response."""
        
        # Validate operation
        operation = params.get("operation")
        if not operation:
            return self._create_error_response(
                "Missing required parameter: 'operation'",
                request_id=request_id
            )
        
        # Initialize encryption and database
        try:
            self._init_cipher()
            self._init_database()
        except Exception as e:
            return self._create_error_response(
                f"Failed to initialize encryption/database: {e}",
                request_id=request_id
            )
        
        # Route to operation handlers
        if operation == "store":
            return self._store_credential(params, request_id)
        elif operation == "retrieve":
            return self._retrieve_credential(params, request_id)
        elif operation == "list":
            return self._list_credentials(params, request_id)
        elif operation == "delete":
            return self._delete_credential(params, request_id)
        elif operation == "update":
            return self._update_credential(params, request_id)
        else:
            return self._create_error_response(
                f"Unknown operation: '{operation}'. Valid operations: store, retrieve, list, delete, update",
                request_id=request_id
            )
    
    def _get_default_db_path(self) -> str:
        """Get default database path from .env or use default."""
        db_path = os.getenv("CREDENTIALS_DB_PATH")
        if not db_path:
            db_path = "persistent/credentials.db"
        return db_path
    
    def _get_encryption_key(self) -> bytes:
        """Generate encryption key from password."""
        password = os.getenv("CREDENTIALS_PASSWORD")
        if not password:
            raise ValueError("Missing CREDENTIALS_PASSWORD in .env")
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'ai-one-credentials-salt',
            iterations=100000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def _init_cipher(self):
        """Initialize encryption cipher."""
        if self.cipher is None:
            self.cipher = Fernet(self._get_encryption_key())
    
    def _init_database(self):
        """Initialize SQLite database."""
        if self.db_path is None:
            self.db_path = self._get_default_db_path()
        
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    encrypted_password BLOB NOT NULL,
                    encrypted_metadata BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _store_credential(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Store encrypted credential."""
        service_name = params.get("service_name")
        username = params.get("username")
        password = params.get("password")
        metadata = params.get("metadata")
        
        if not all([service_name, username, password]):
            return self._create_error_response(
                "Missing required parameters: 'service_name', 'username', 'password'",
                request_id=request_id
            )
        
        try:
            encrypted_password = self.cipher.encrypt(password.encode())
            
            encrypted_metadata = None
            if metadata:
                # Validate JSON if provided
                if isinstance(metadata, str):
                    json.loads(metadata)  # Validate JSON string
                    encrypted_metadata = self.cipher.encrypt(metadata.encode())
                else:
                    # Convert dict to JSON string
                    metadata_str = json.dumps(metadata)
                    encrypted_metadata = self.cipher.encrypt(metadata_str.encode())
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO credentials (service_name, username, encrypted_password, encrypted_metadata)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(service_name) DO UPDATE SET
                        username = excluded.username,
                        encrypted_password = excluded.encrypted_password,
                        encrypted_metadata = excluded.encrypted_metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, (service_name, username, encrypted_password, encrypted_metadata))
                conn.commit()
                
                was_update = cursor.rowcount == 0  # ON CONFLICT UPDATE doesn't change rowcount
            
            return self._create_success_response(
                result={
                    "action": "updated" if was_update else "stored",
                    "service_name": service_name,
                    "username": username,
                    "has_metadata": metadata is not None,
                    "message": f"Credential {'updated' if was_update else 'stored'} for '{service_name}'"
                },
                request_id=request_id
            )
            
        except json.JSONDecodeError:
            return self._create_error_response(
                "Invalid JSON in metadata",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Error storing credential: {e}",
                request_id=request_id
            )
    
    def _retrieve_credential(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Retrieve and decrypt credential."""
        service_name = params.get("service_name")
        if not service_name:
            return self._create_error_response(
                "Missing required parameter: 'service_name'",
                request_id=request_id
            )
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT username, encrypted_password, encrypted_metadata, created_at, updated_at
                    FROM credentials WHERE service_name = ?
                """, (service_name,))
                row = cursor.fetchone()
            
            if not row:
                return self._create_error_response(
                    f"No credentials found for service '{service_name}'",
                    request_id=request_id
                )
            
            username, encrypted_password, encrypted_metadata, created_at, updated_at = row
            
            # Decrypt password
            decrypted_password = self.cipher.decrypt(encrypted_password).decode()
            
            # Decrypt metadata if present
            decrypted_metadata = None
            if encrypted_metadata:
                decrypted_metadata = self.cipher.decrypt(encrypted_metadata).decode()
                try:
                    # Try to parse as JSON
                    decrypted_metadata = json.loads(decrypted_metadata)
                except json.JSONDecodeError:
                    # Keep as string if not valid JSON
                    pass
            
            return self._create_success_response(
                result={
                    "service_name": service_name,
                    "username": username,
                    "password": decrypted_password,
                    "metadata": decrypted_metadata,
                    "created_at": created_at,
                    "updated_at": updated_at
                },
                request_id=request_id
            )
            
        except Exception as e:
            return self._create_error_response(
                f"Error retrieving credential: {e}",
                request_id=request_id
            )
    
    def _list_credentials(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """List all stored credentials (without passwords)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT service_name, username, created_at, updated_at,
                           CASE WHEN encrypted_metadata IS NOT NULL THEN 1 ELSE 0 END as has_metadata
                    FROM credentials ORDER BY service_name
                """)
                rows = cursor.fetchall()
            
            credentials = []
            for row in rows:
                service_name, username, created_at, updated_at, has_metadata = row
                credentials.append({
                    "service_name": service_name,
                    "username": username,
                    "has_metadata": bool(has_metadata),
                    "created_at": created_at,
                    "updated_at": updated_at
                })
            
            return self._create_success_response(
                result={
                    "credentials": credentials,
                    "total_count": len(credentials),
                    "database_path": self.db_path
                },
                request_id=request_id
            )
            
        except Exception as e:
            return self._create_error_response(
                f"Error listing credentials: {e}",
                request_id=request_id
            )
    
    def _delete_credential(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Delete a stored credential."""
        service_name = params.get("service_name")
        if not service_name:
            return self._create_error_response(
                "Missing required parameter: 'service_name'",
                request_id=request_id
            )
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM credentials WHERE service_name = ?
                """, (service_name,))
                conn.commit()
                
                if cursor.rowcount == 0:
                    return self._create_error_response(
                        f"No credentials found for service '{service_name}'",
                        request_id=request_id
                    )
            
            return self._create_success_response(
                result={
                    "action": "deleted",
                    "service_name": service_name,
                    "message": f"Credential deleted for '{service_name}'"
                },
                request_id=request_id
            )
            
        except Exception as e:
            return self._create_error_response(
                f"Error deleting credential: {e}",
                request_id=request_id
            )
    
    def _update_credential(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Update existing credential."""
        return self._store_credential(params, request_id)  # Same logic as store
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return """Credentials Tool

DESCRIPTION:
    Manages encrypted credentials stored in SQLite database.
    Uses Fernet encryption (AES 128) with PBKDF2 key derivation.

OPERATIONS:
    store      - Store new credential (or update existing)
    retrieve   - Get credential with decrypted password
    list       - List all credentials (without passwords)
    delete     - Remove credential
    update     - Update existing credential (same as store)

PARAMETERS:
    operation (string, required)
        Operation to perform

    service_name (string, required for most operations)
        Unique identifier for the service/credential

    username (string, required for store/update)
        Username for the credential

    password (string, required for store/update)
        Password to encrypt and store

    metadata (string/object, optional)
        Additional data (JSON string or object)

EXAMPLES:
    1. Store credential:
       {"operation": "store", "service_name": "github", "username": "user123", "password": "secret123"}

    2. Store with metadata:
       {"operation": "store", "service_name": "api", "username": "admin", "password": "key", "metadata": {"url": "https://api.example.com", "env": "prod"}}

    3. Retrieve credential:
       {"operation": "retrieve", "service_name": "github"}

    4. List all credentials:
       {"operation": "list"}

    5. Delete credential:
       {"operation": "delete", "service_name": "github"}

CONFIGURATION:
    Set in .env file:
        CREDENTIALS_PASSWORD=your_master_password
        CREDENTIALS_DB_PATH=persistent/credentials.db  # optional

SECURITY:
    - Master password required for encryption
    - Uses PBKDF2 with 100,000 iterations
    - AES-128 encryption via Fernet
    - Database stored locally only
    - Passwords never stored in plain text

RESPONSE FORMAT:
    Success:
        {
            "status": "success",
            "result": {
                "service_name": "github",
                "username": "user123",
                "password": "secret123",  // only in retrieve
                "metadata": {...},
                "created_at": "2023-01-01 12:00:00",
                "updated_at": "2023-01-01 12:00:00"
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
    - Database created automatically on first use
    - Master password cannot be changed once set
    - Use strong master password
    - Backup credentials.db file regularly
    - service_name must be unique per credential
"""