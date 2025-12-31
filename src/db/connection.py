"""
SQL Server Database Connection Module
======================================
Provides connection pool and utilities for SQL Server.
"""

import pyodbc
from typing import Optional, Generator
from contextlib import contextmanager

from src.config import get_config, DatabaseConfig


# Connection pool (simple implementation)
_connection_pool: list[pyodbc.Connection] = []
_pool_size: int = 5


def create_connection(config: Optional[DatabaseConfig] = None) -> pyodbc.Connection:
    """
    Create a new SQL Server connection.
    
    Args:
        config: Optional database config. Uses global config if not provided.
        
    Returns:
        pyodbc Connection object
    """
    if config is None:
        config = get_config().db
    
    conn = pyodbc.connect(config.connection_string, autocommit=False)
    return conn


def get_connection() -> pyodbc.Connection:
    """
    Get a connection from the pool or create a new one.
    
    Returns:
        pyodbc Connection object
    """
    global _connection_pool
    
    # Try to get an existing connection from the pool
    while _connection_pool:
        conn = _connection_pool.pop()
        try:
            # Test if connection is still alive
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return conn
        except pyodbc.Error:
            # Connection is dead, discard it
            try:
                conn.close()
            except:
                pass
            continue
    
    # No available connections, create a new one
    return create_connection()


def release_connection(conn: pyodbc.Connection) -> None:
    """
    Return a connection to the pool.
    
    Args:
        conn: Connection to return
    """
    global _connection_pool
    
    if len(_connection_pool) < _pool_size:
        try:
            conn.rollback()  # Clear any pending transaction
            _connection_pool.append(conn)
        except pyodbc.Error:
            # Connection is broken, discard it
            try:
                conn.close()
            except:
                pass
    else:
        # Pool is full, close the connection
        try:
            conn.close()
        except:
            pass


@contextmanager
def get_db_connection() -> Generator[pyodbc.Connection, None, None]:
    """
    Context manager for database connections.
    Automatically handles connection acquisition and release.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs")
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_connection(conn)


def execute_query(sql: str, params: tuple = ()) -> list[dict]:
    """
    Execute a SELECT query and return results as list of dicts.
    
    Args:
        sql: SQL query string
        params: Query parameters
        
    Returns:
        List of dictionaries with column names as keys
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        
        columns = [column[0] for column in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        return results


def execute_non_query(sql: str, params: tuple = ()) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query.
    
    Args:
        sql: SQL query string
        params: Query parameters
        
    Returns:
        Number of rows affected
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.rowcount


def test_connection() -> bool:
    """
    Test if database connection works.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            print(f"Connected to SQL Server: {version[:50]}...")
            return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing SQL Server connection...")
    if test_connection():
        print("✅ Connection successful!")
    else:
        print("❌ Connection failed!")
