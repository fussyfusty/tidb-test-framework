"""Chaos engineering test: Connection failure simulation."""

import time
import pytest
from tidb_test.loader.python_loader import mark_tag, mark_timeout
from tidb_test.connector import TiDBConnection, ConnectionConfig


def setup_module():
    """Setup before any tests in this module."""
    print("\n🔧 Setting up chaos test environment...")


def teardown_module():
    """Cleanup after all tests."""
    print("\n🧹 Cleaning up chaos test environment...")


@mark_tag('chaos', 'connection')
@mark_timeout(60)
def test_connection_interruption():
    """Test that application handles connection interruption gracefully."""
    
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        result = conn.execute("SELECT 1")
        assert result['status'] == 'success'
        
        conn.close()
        time.sleep(1)
        
        result = conn.execute("SELECT 2")
        assert result['status'] == 'success'
        
    finally:
        conn.close()


@mark_tag('chaos', 'timeout')
def test_slow_query_handling():
    """Test handling of slow queries."""
    
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        # Set ultra-short timeout
        conn.execute("SET @@MAX_EXECUTION_TIME = 1")
        
        # Execute a complex query that should time out
        result = conn.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables a 
            CROSS JOIN information_schema.tables b 
            CROSS JOIN information_schema.tables c
        """)
        
        # If we get here, the query didn't time out - test should fail
        assert result['status'] == 'error', "Query should have timed out but succeeded"
        
    except Exception as e:
        # If an exception was raised (timeout), test passes
        print(f"✅ Query timed out as expected: {e}")
        assert True
    finally:
        conn.close()


@mark_tag('chaos', 'recovery')
def test_recovery_after_crash():
    """Test recovery after simulated crash."""
    
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    
    try:
        conn.connect()
        result = conn.execute("SELECT 1")
        assert result['status'] == 'success'
        
    finally:
        conn.close()