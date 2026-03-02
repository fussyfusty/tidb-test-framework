"""Flaky test detection: Timing-sensitive tests."""

import time
import pytest
from tidb_test.loader.python_loader import mark_tag
from tidb_test.connector import TiDBConnection, ConnectionConfig


@mark_tag('flaky', 'timing')
def test_slow_query_timing():
    """Test that slow queries might be flaky."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_slow (id INT PRIMARY KEY, data VARCHAR(1000))")
        for i in range(100):
            conn.execute("INSERT INTO test_slow VALUES (%s, REPEAT('x', 500))", (i,))
        
        # Escape the % sign by using %%
        start = time.time()
        result = conn.execute("SELECT COUNT(*) FROM test_slow WHERE data LIKE '%%x%%'")
        duration = time.time() - start
        
        print(f"Query took {duration:.3f}s")
        assert result['status'] == 'success'
        assert result['data'][0][0] == 100
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_slow")
        conn.close()


@mark_tag('flaky', 'timing')
def test_timeout_sensitive():
    """Test that timeout settings might cause flakiness."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("SET @@MAX_EXECUTION_TIME = 10")
        
        try:
            result = conn.execute("SELECT BENCHMARK(10000000, 1+1)")
            assert result['status'] == 'success'
        except Exception as e:
            print(f"Query timed out as expected: {e}")
            
    finally:
        conn.close()
