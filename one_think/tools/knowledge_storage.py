"""
Knowledge Database Storage Manager

Handles SQLite database initialization, migrations, and connection management
for the knowledge database tool.
"""

import sqlite3
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class KnowledgeDBStorage:
    """Manages persistent storage for the knowledge database."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize storage manager.
        
        Args:
            db_path: Path to SQLite database file. Uses default if None.
        """
        if db_path is None:
            # Default location in persistent folder (from project root)
            project_root = Path(__file__).parent.parent.parent  # go up to ai-one root
            persistent_dir = project_root / "persistent"
            persistent_dir.mkdir(exist_ok=True)
            db_path = persistent_dir / "knowledge.db"
        
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None
        self._ensure_initialized()
    
    def _ensure_initialized(self):
        """Ensure database is initialized with proper schema."""
        try:
            # Create database if it doesn't exist
            if not self.db_path.exists():
                logger.info(f"Creating new knowledge database: {self.db_path}")
                self._create_database()
            else:
                logger.info(f"Using existing knowledge database: {self.db_path}")
                # Verify schema is current
                self._verify_schema()
                
        except Exception as e:
            logger.error(f"Failed to initialize knowledge database: {e}")
            raise
    
    def _create_database(self):
        """Create new database with schema."""
        schema_path = self.db_path.parent / "knowledge_db_schema.sql"
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        conn = self.get_connection()
        try:
            # Execute schema creation
            conn.executescript(schema_sql)
            conn.commit()
            logger.info("Knowledge database schema created successfully")
        except Exception as e:
            logger.error(f"Failed to create database schema: {e}")
            raise
        finally:
            conn.close()
    
    def _verify_schema(self):
        """Verify database has required tables and structure."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if main table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='knowledge_entries'
            """)
            
            if not cursor.fetchone():
                logger.warning("knowledge_entries table not found, recreating schema")
                self._create_database()
                return
            
            # Check if FTS table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='knowledge_fts'
            """)
            
            if not cursor.fetchone():
                logger.warning("knowledge_fts table not found, recreating schema")
                self._create_database()
                return
                
            logger.debug("Database schema verification passed")
            
        except Exception as e:
            logger.error(f"Schema verification failed: {e}")
            raise
        finally:
            conn.close()
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get database connection.
        
        Returns:
            SQLite connection object
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return results as list of dictionaries.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result rows as dictionaries
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            # Convert rows to dictionaries
            columns = [description[0] for description in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
        finally:
            conn.close()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """
        Execute INSERT/UPDATE/DELETE query.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            
            return cursor.rowcount
            
        except Exception as e:
            logger.error(f"Update execution failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """
        Execute INSERT query and return last inserted row ID.
        
        Args:
            query: SQL INSERT query string
            params: Query parameters
            
        Returns:
            ID of inserted row
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            
            return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Insert execution failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with database stats
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get entry count
            cursor.execute("SELECT COUNT(*) as count FROM knowledge_entries")
            entry_count = cursor.fetchone()[0]
            
            # Get most accessed entry
            cursor.execute("""
                SELECT question, access_count 
                FROM knowledge_entries 
                ORDER BY access_count DESC 
                LIMIT 1
            """)
            most_accessed = cursor.fetchone()
            
            # Get database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            return {
                'entry_count': entry_count,
                'most_accessed_question': most_accessed[0] if most_accessed else None,
                'max_access_count': most_accessed[1] if most_accessed else 0,
                'database_size_bytes': db_size,
                'database_path': str(self.db_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {'error': str(e)}
        finally:
            conn.close()
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """
        Create backup of the database.
        
        Args:
            backup_path: Path for backup file. Auto-generated if None.
            
        Returns:
            Path to backup file
        """
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.db_path.parent / f"knowledge_backup_{timestamp}.db"
        
        backup_path = Path(backup_path)
        
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise
    
    def close(self):
        """Close database connection if open."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Global instance for easy access
_storage_instance: Optional[KnowledgeDBStorage] = None

def get_storage() -> KnowledgeDBStorage:
    """Get global knowledge database storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = KnowledgeDBStorage()
    return _storage_instance