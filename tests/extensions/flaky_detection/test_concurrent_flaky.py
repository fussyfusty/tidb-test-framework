"""Flaky test detection: Concurrent execution tests."""

import pytest
import threading
import time
from tidb_test.loader.python_loader import mark_tag
from tidb_test.connector import TiDBConnection, ConnectionConfig


@mark_tag('flaky', 'concurrent')
def test_concurrent_read_write():
    """Test potential flakiness in concurrent read/write."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_concurrent (id INT PRIMARY KEY, value INT)")
        conn.execute("INSERT INTO test_concurrent VALUES (1, 100)")
        
        results = []
        
        def reader():
            local_conn = TiDBConnection(config)
            local_conn.connect()
            for _ in range(10):
                result = local_conn.execute("SELECT value FROM test_concurrent WHERE id = 1")
                results.append(result['data'][0][0])
                time.sleep(0.01)
            local_conn.close()
        
        def writer():
            local_conn = TiDBConnection(config)
            local_conn.connect()
            for i in range(5):
                local_conn.execute("UPDATE test_concurrent SET value = %s WHERE id = 1", (100 + i,))
                time.sleep(0.02)
            local_conn.close()
        
        # Run concurrent threads
        t1 = threading.Thread(target=reader)
        t2 = threading.Thread(target=writer)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Should see various values (potential flakiness)
        assert len(set(results)) > 1
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_concurrent")
        conn.close()


@mark_tag('flaky', 'concurrent')
def test_concurrent_transactions():
    """Test flakiness in concurrent transactions."""
    config = ConnectionConfig(host='127.0.0.1', port=4000)
    conn = TiDBConnection(config)
    conn.connect()
    
    try:
        conn.execute("CREATE TABLE test_txn_flaky (id INT PRIMARY KEY, value INT)")
        conn.execute("INSERT INTO test_txn_flaky VALUES (1, 100)")
        
        success_count = 0
        
        def txn_operation(txn_id):
            local_conn = TiDBConnection(config)
            local_conn.connect()
            try:
                local_conn.execute("BEGIN")
                result = local_conn.execute("SELECT value FROM test_txn_flaky WHERE id = 1")
                current = result['data'][0][0]
                local_conn.execute("UPDATE test_txn_flaky SET value = %s WHERE id = 1", (current + 1,))
                local_conn.execute("COMMIT")
                return True
            except Exception:
                local_conn.execute("ROLLBACK")
                return False
            finally:
                local_conn.close()
        
        threads = []
        for i in range(5):
            t = threading.Thread(target=lambda: success_count + txn_operation(i))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Some transactions may fail due to conflicts (flaky)
        final_result = conn.execute("SELECT value FROM test_txn_flaky WHERE id = 1")
        print(f"Final value: {final_result['data'][0][0]}")
        
    finally:
        conn.execute("DROP TABLE IF EXISTS test_txn_flaky")
        conn.close()
