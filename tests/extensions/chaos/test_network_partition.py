"""Chaos engineering: Network partition simulation."""

import time
import pytest
from tidb_test.loader.python_loader import mark_tag
from tidb_test.connector import TiDBConnection, ConnectionConfig


@mark_tag('chaos', 'network')
def test_connection_interruption():
    """Test reconnection after network interruption."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        # Normal query
        result = conn.execute("SELECT 1")
        assert result['status'] == 'success'
        
        # Simulate network drop by closing and reopening
        conn.close()
        time.sleep(2)
        conn.connect()
        
        # Should work after reconnection
        result = conn.execute("SELECT 2")
        assert result['status'] == 'success'
        
    finally:
        conn.close()


@mark_tag('chaos', 'network')
def test_connection_timeout():
    """Test connection timeout handling."""
    # Use wrong port to simulate network unreachable
    config = ConnectionConfig(host='127.0.0.1', port=9999, timeout=1)
    
    try:
        conn = TiDBConnection(config)
        conn.connect()
        assert False, "Should not connect"
    except Exception as e:
        assert "Connection refused" in str(e) or "timeout" in str(e)
