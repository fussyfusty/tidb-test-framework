"""Database connection management for TiDB testing."""

import pymysql
import time
import logging
from typing import Optional, Any, Dict, List, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

from tidb_test.exceptions import ConnectionError, ExecutionError


@dataclass
class ConnectionConfig:
    """Configuration for TiDB connection."""
    host: str = "127.0.0.1"
    port: int = 4000
    user: str = "root"
    password: str = ""
    database: str = "test"
    charset: str = "utf8mb4"
    autocommit: bool = True
    timeout: int = 30
    
    @classmethod
    def from_dict(cls, config: Dict) -> 'ConnectionConfig':
        """Create config from dictionary."""
        return cls(**{k: v for k, v in config.items() if k in cls.__annotations__})


class TiDBConnection:
    """Manages connection to TiDB with error handling."""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connection: Optional[pymysql.Connection] = None
        self.logger = logging.getLogger(__name__)
        self._connected = False
        
    def connect(self) -> None:
        """Establish connection to TiDB."""
        try:
            self.connection = pymysql.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset=self.config.charset,
                autocommit=self.config.autocommit,
                connect_timeout=self.config.timeout
            )
            self._connected = True
            self.logger.info(f"Connected to TiDB at {self.config.host}:{self.config.port}")
        except pymysql.Error as e:
            raise ConnectionError(f"Failed to connect to TiDB: {e}") from e
    
    def execute(self, sql: str, params: Optional[tuple] = None, retry: int = 0) -> Dict[str, Any]:
        """Execute SQL with retry logic."""
        last_error = None
        
        for attempt in range(retry + 1):
            try:
                if not self._connected or not self.connection:
                    self.connect()
                
                cursor = self.connection.cursor()
                cursor.execute(sql, params or ())
                
                # Check if this is a SELECT query
                if sql.strip().upper().startswith("SELECT"):
                    data = cursor.fetchall()
                    return {
                        "status": "success",
                        "data": data,
                        "affected_rows": cursor.rowcount,
                        "error": None
                    }
                else:
                    self.connection.commit()
                    return {
                        "status": "success",
                        "data": None,
                        "affected_rows": cursor.rowcount,
                        "error": None
                    }
                    
            except pymysql.Error as e:
                last_error = e
                if attempt < retry:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    self._connected = False  # Force reconnect
                    continue
                    
                error_info = {
                    "status": "error",
                    "data": None,
                    "affected_rows": 0,
                    "error": {
                        "code": e.args[0] if e.args else "unknown",
                        "message": str(e),
                        "sql": sql
                    }
                }
                
                self.logger.error(f"SQL execution failed after {retry} retries: {e}")
                return error_info
            finally:
                if 'cursor' in locals():
                    cursor.close()
        
        # If we get here, all retries failed
        return {
            "status": "error",
            "data": None,
            "affected_rows": 0,
            "error": {
                "code": last_error.args[0] if last_error and last_error.args else "unknown",
                "message": str(last_error) if last_error else "Unknown error",
                "sql": sql
            }
        }
    
    @contextmanager
    def transaction(self):
        """Context manager for transaction handling."""
        try:
            self.connection.begin()
            yield
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise ExecutionError(f"Transaction failed: {e}") from e
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self._connected = False
            self.logger.info("Database connection closed")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def get_server_version(self) -> str:
        """Get TiDB server version."""
        result = self.execute("SELECT VERSION()")
        if result["status"] == "success" and result["data"]:
            return result["data"][0][0]
        return "unknown"
    
    def reset_connection(self) -> None:
        """Force reset the connection."""
        self.close()
        time.sleep(1)
        self.connect()