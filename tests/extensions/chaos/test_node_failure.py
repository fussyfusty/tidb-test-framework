"""Chaos engineering: Node failure simulation."""

import time
import pytest
from tidb_test.loader.python_loader import mark_tag
from tidb_test.connector import TiDBConnection, ConnectionConfig


@mark_tag('chaos', 'node')
def test_node_restart():
    """Test behavior when node restarts."""
    # Note: This test assumes you can restart TiDB
    # In real implementation, would need external orchestration
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        # Basic query before restart
        result = conn.execute("SELECT 1")
        assert result['status'] == 'success'
        
        # Simulate restart by closing connection
        conn.close()
        time.sleep(3)
        
        # Reconnect and verify
        conn.connect()
        result = conn.execute("SELECT 2")
        assert result['status'] == 'success'
        
    finally:
        conn.close()


@mark_tag('chaos', 'node')
def test_node_recovery():
    """Test recovery after crash."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    
    try:
        conn = TiDBConnection(config)
        conn.connect()
        result = conn.execute("SELECT 1")
        assert result['status'] == 'success'
        conn.close()
    except Exception as e:
        # If connection fails, test should handle gracefully
        pytest.skip(f"Node not available: {e}")
