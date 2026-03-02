"""Distributed systems: Two-Phase Commit tests."""

import pytest
from tidb_test.loader.python_loader import mark_tag
from tidb_test.connector import TiDBConnection, ConnectionConfig


@mark_tag('distributed', '2pc')
def test_two_phase_commit_basic():
    """Basic 2PC transaction test."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_2pc (id INT PRIMARY KEY, value INT)")
        
        conn.execute("BEGIN")
        conn.execute("INSERT INTO test_2pc VALUES (1, 100)")
        conn.execute("INSERT INTO test_2pc VALUES (2, 200)")
        conn.execute("COMMIT")
        
        result = conn.execute("SELECT COUNT(*) FROM test_2pc")
        assert result['data'][0][0] == 2
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_2pc")
        conn.close()


@mark_tag('distributed', '2pc')
def test_2pc_rollback():
    """2PC rollback test."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_2pc_rollback (id INT PRIMARY KEY, value INT)")
        
        conn.execute("BEGIN")
        conn.execute("INSERT INTO test_2pc_rollback VALUES (1, 100)")
        conn.execute("ROLLBACK")
        
        result = conn.execute("SELECT COUNT(*) FROM test_2pc_rollback")
        assert result['data'][0][0] == 0
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_2pc_rollback")
        conn.close()
