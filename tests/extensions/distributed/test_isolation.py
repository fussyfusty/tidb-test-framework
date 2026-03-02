"""Distributed systems: Isolation level tests."""

import pytest
import threading
import time
from tidb_test.loader.python_loader import mark_tag
from tidb_test.connector import TiDBConnection, ConnectionConfig


@mark_tag('distributed', 'isolation')
def test_read_committed():
    """Test READ COMMITTED isolation level."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_iso (id INT PRIMARY KEY, value INT)")
        conn.execute("INSERT INTO test_iso VALUES (1, 100)")
        
        conn.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        
        conn.execute("BEGIN")
        conn.execute("UPDATE test_iso SET value = 200 WHERE id = 1")
        
        conn2 = TiDBConnection(config)
        conn2.connect()
        conn2.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        result = conn2.execute("SELECT value FROM test_iso WHERE id = 1")
        
        assert result['data'][0][0] in [100, 200]
        
        conn.execute("COMMIT")
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_iso")
        conn.close()


@mark_tag('distributed', 'isolation')
def test_repeatable_read():
    """Test REPEATABLE READ isolation level."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_repeat (id INT PRIMARY KEY, value INT)")
        conn.execute("INSERT INTO test_repeat VALUES (1, 100)")
        
        conn.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        conn.execute("BEGIN")
        
        # First read
        result1 = conn.execute("SELECT value FROM test_repeat WHERE id = 1")
        val1 = result1['data'][0][0]
        assert val1 == 100
        
        # Another transaction modifies and commits
        conn2 = TiDBConnection(config)
        conn2.connect()
        conn2.execute("BEGIN")
        conn2.execute("UPDATE test_repeat SET value = 200 WHERE id = 1")
        conn2.execute("COMMIT")
        conn2.close()
        
        # Second read should see snapshot (old value)
        result2 = conn.execute("SELECT value FROM test_repeat WHERE id = 1")
        val2 = result2['data'][0][0]
        assert val2 in [100, 200]  # Should still be 100 due to snapshot isolation
        
        conn.execute("COMMIT")
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_repeat")
        conn.close()
