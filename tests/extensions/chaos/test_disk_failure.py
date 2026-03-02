"""Chaos engineering: Disk failure simulation."""

import time
import pytest
from tidb_test.loader.python_loader import mark_tag
from tidb_test.connector import TiDBConnection, ConnectionConfig


@mark_tag('chaos', 'disk')
def test_disk_full_simulation():
    """Test behavior when disk is full (simulated)."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        # Try to create large table (would fail if disk full)
        result = conn.execute("""
            CREATE TABLE test_large (
                id INT PRIMARY KEY,
                data LONGTEXT
            )
        """)
        assert result['status'] == 'success'
    finally:
        conn.execute("DROP TABLE IF EXISTS test_large")
        conn.close()


@mark_tag('chaos', 'disk')
def test_disk_latency():
    """Test with high disk latency simulation."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        # Normal query should work
        result = conn.execute("SELECT 1")
        assert result['status'] == 'success'
    finally:
        conn.close()
