"""Distributed systems: Consistency tests."""

import pytest
from tidb_test.loader.python_loader import mark_tag
from tidb_test.connector import TiDBConnection, ConnectionConfig


@mark_tag('distributed', 'consistency')
def test_linearizability():
    """Test linearizable consistency."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_linear (id INT PRIMARY KEY, value INT)")
        
        # Write
        conn.execute("INSERT INTO test_linear VALUES (1, 100)")
        
        # Read should see the write immediately
        result = conn.execute("SELECT value FROM test_linear WHERE id = 1")
        assert result['data'][0][0] == 100
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_linear")
        conn.close()


@mark_tag('distributed', 'consistency')
def test_causal_consistency():
    """Test causal consistency."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_causal (id INT PRIMARY KEY, value INT, version INT)")
        
        # Transaction 1
        conn.execute("BEGIN")
        conn.execute("INSERT INTO test_causal VALUES (1, 100, 1)")
        conn.execute("COMMIT")
        
        # Transaction 2 (causally dependent)
        conn.execute("BEGIN")
        result = conn.execute("SELECT value FROM test_causal WHERE id = 1")
        new_value = result['data'][0][0] + 50
        conn.execute("UPDATE test_causal SET value = %s, version = 2 WHERE id = 1", (new_value,))
        conn.execute("COMMIT")
        
        # Verify
        result = conn.execute("SELECT value, version FROM test_causal WHERE id = 1")
        assert result['data'][0] == (150, 2)
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_causal")
        conn.close()
