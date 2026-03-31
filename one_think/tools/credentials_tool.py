from one_think.tools import Tool
import sqlite3
import os
import base64
import json
from typing import Any, Dict, Tuple
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

load_dotenv()


class CredentialsTool(Tool):
    """
    Tool for managing encrypted credentials in SQLite.
    """

    name: str = "credentials"
    description: str = "Manages encrypted credentials stored in SQLite database."


    def __init__(self):
        super().__init__()
        self.db_path: str | None = None
        self.cipher: Fernet | None = None
    
    def _get_default_db_path(self) -> str:
        """Get default database path from .env or use default."""
        db_path = os.getenv("CREDENTIALS_DB_PATH")
        if not db_path:
            db_path = "persistent/credentials.db"
        return db_path

    def _get_encryption_key(self) -> bytes:
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
        if self.cipher is None:
            self.cipher = Fernet(self._get_encryption_key())

    def _init_database(self):
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

    def _store(self, service_name: str, username: str, password: str, metadata: str | None):
        if not service_name or not username or not password:
            return "", "Missing required arguments for 'store': service_name, username, password"

        try:
            encrypted_password = self.cipher.encrypt(password.encode())

            encrypted_metadata = None
            if metadata:
                json.loads(metadata)
                encrypted_metadata = self.cipher.encrypt(metadata.encode())

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO credentials (service_name, username, encrypted_password, encrypted_metadata)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(service_name) DO UPDATE SET
                        username = excluded.username,
                        encrypted_password = excluded.encrypted_password,
                        encrypted_metadata = excluded.encrypted_metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, (service_name, username, encrypted_password, encrypted_metadata))
                conn.commit()

            return f"Stored credentials for '{service_name}'", ""

        except json.JSONDecodeError:
            return "", "Metadata must be valid JSON"
        except Exception as e:
            return "", f"Store error: {e}"

    def _list(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("""
                    SELECT service_name, username, created_at, updated_at
                    FROM credentials
                    ORDER BY service_name
                """).fetchall()

            if not rows:
                return json.dumps({"count": 0, "services": []}, indent=2), ""

            result = {
                "count": len(rows),
                "services": [
                    {
                        "service_name": row[0],
                        "username": row[1],
                        "created_at": row[2],
                        "updated_at": row[3]
                    }
                    for row in rows
                ]
            }
            return json.dumps(result, indent=2), ""

        except Exception as e:
            return "", f"List error: {e}"

    def _get_credentials(self, service_name: str):
        if not service_name:
            return "", "Missing required argument for 'get_credentials': service_name"

        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("""
                    SELECT username, encrypted_password, encrypted_metadata
                    FROM credentials
                    WHERE service_name = ?
                """, (service_name,)).fetchone()

            if not row:
                return "", f"No credentials for '{service_name}'"

            username, encrypted_password, encrypted_metadata = row

            result = {
                "service_name": service_name,
                "username": username,
                "password": self.cipher.decrypt(encrypted_password).decode()
            }

            if encrypted_metadata:
                metadata_json = self.cipher.decrypt(encrypted_metadata).decode()
                result["metadata"] = json.loads(metadata_json)

            return json.dumps(result, indent=2), ""

        except Exception as e:
            return "", f"Get credentials error: {e}"

    def _delete(self, service_name: str):
        if not service_name:
            return "", "Missing required argument for 'delete': service_name"

        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute(
                    "DELETE FROM credentials WHERE service_name = ?",
                    (service_name,)
                )
                conn.commit()

            if cur.rowcount > 0:
                return f"Deleted '{service_name}'", ""

            return "", f"No credentials for '{service_name}'"

        except Exception as e:
            return "", f"Delete error: {e}"

    def execute(self, arguments: Dict[str, Any] | None = None) -> Tuple[str, str]:
        arguments = arguments or {}

        if arguments.get("help"):
            return self.get_full_information(), ""

        operation = arguments.get("operation")
        if not operation:
            return "", "Missing required argument: 'operation'"

        self.db_path = arguments.get("db_path", self._get_default_db_path())

        try:
            self._init_cipher()
            self._init_database()
        except Exception as e:
            return "", f"Init error: {e}"

        if operation == "store":
            return self._store(
                arguments.get("service_name"),
                arguments.get("username"),
                arguments.get("password"),
                arguments.get("metadata")
            )

        if operation == "list":
            return self._list()

        if operation == "get_credentials":
            return self._get_credentials(arguments.get("service_name"))

        if operation == "delete":
            return self._delete(arguments.get("service_name"))

        return "", (
            f"Unknown operation: '{operation}'. "
            "Valid operations: store, list, get_credentials, delete"
        )

    def get_full_information(self) -> str:
        return (
            f"Tool: {self.name}\n"
            "Description: Manages encrypted credentials in SQLite.\n\n"
            "Operations:\n"
            "- store: save or update credentials\n"
            "- list: list stored entries without passwords\n"
            "- get_credentials: return full credentials for one service\n"
            "- delete: remove credentials for one service\n\n"
            "Arguments:\n"
            "- operation (str): required\n"
            "- service_name (str): required for get_credentials and delete\n"
            "- username (str): required for store\n"
            "- password (str): required for store\n"
            "- metadata (str): optional JSON string\n"
            "- db_path (str): optional, default='credentials.db'\n"
            "- help (bool): show this message\n"
        )


if __name__ == "__main__":
    tool = CredentialsTool()

    print("\n--- HELP ---")
    print(tool.execute({"help": True})[0])

    print("\n--- STORE ---")
    print(tool.execute({
        "operation": "store",
        "service_name": "github",
        "username": "user@example.com",
        "password": "secret123",
        "metadata": '{"token": "abc123"}'
    }))

    print("\n--- LIST ---")
    print(tool.execute({
        "operation": "list"
    }))

    print("\n--- GET CREDENTIALS ---")
    print(tool.execute({
        "operation": "get_credentials",
        "service_name": "github"
    }))