#!/usr/bin/env python3
"""
Benchmark & Performance Test Script for BE-003: "Add to batch" Wizard
Target: WujiaTea ERP (Odoo 19) — Module wujia_delivery
Simulates single & batch execution speed on large dataset.
"""

import sys
import time
import psycopg2

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

DB_HOST = "127.0.0.1"
DB_PORT = 5433
DB_NAME = "wujia_db"
DB_USER = "odoo19"
DB_PASS = "1"

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def ensure_picking_type_flag(cur):
    """Ensure outgoing picking type has requires_transport_planning = True."""
    cur.execute("""
        UPDATE stock_picking_type 
        SET requires_transport_planning = TRUE 
        WHERE code = 'outgoing';
    """)

def count_records(cur):
    cur.execute("SELECT count(*) FROM stock_picking;")
    pickings = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM stock_picking_batch;")
    batches = cur.fetchone()[0]
    return pickings, batches

def seed_simulation_data(cur, count=100000):
    """Seed historical simulated data representing multi-year volume."""
    print(f"\n[*] Generating {count:,} historical picking records...")
    start_t = time.perf_counter()
    
    # Generate batches first
    batch_count = max(count // 10, 1000)
    cur.execute(f"""
        INSERT INTO stock_picking_batch (name, state, company_id, delivery_batch_status, is_wave, create_date, write_date)
        SELECT 
            'PERF/BATCH/' || LPAD(i::text, 7, '0'),
            'done',
            1,
            'done',
            false,
            NOW() - (random() * interval '1800 days'),
            NOW()
        FROM generate_series(1, {batch_count}) AS i
        RETURNING id;
    """)
    batch_ids = [r[0] for r in cur.fetchall()]
    min_b_id = min(batch_ids)
    max_b_id = max(batch_ids)
    
    # Generate done pickings attached to batches
    cur.execute(f"""
        INSERT INTO stock_picking (
            name, state, picking_type_id, location_id, location_dest_id, 
            move_type, company_id, batch_id, scheduled_date, 
            planned_weight, delivery_status, create_date, write_date
        )
        SELECT 
            'PERF/PICK/' || LPAD(i::text, 8, '0'),
            'done',
            2,
            5,
            2,
            'direct',
            1,
            (floor(random() * ({max_b_id} - {min_b_id} + 1)) + {min_b_id})::int,
            NOW() - (random() * interval '1800 days'),
            (random() * 50 + 5)::numeric(10,2),
            'done',
            NOW() - (random() * interval '1800 days'),
            NOW()
        FROM generate_series(1, {count}) AS i;
    """)
    
    # Generate 50 fresh active pickings in Pending Queue for test
    cur.execute("""
        INSERT INTO stock_picking (
            name, state, picking_type_id, location_id, location_dest_id, 
            move_type, company_id, batch_id, scheduled_date, 
            planned_weight, delivery_status, create_date, write_date
        )
        SELECT 
            'PERF/ACTIVE/' || LPAD(i::text, 4, '0'),
            'assigned',
            2,
            5,
            2,
            'direct',
            1,
            NULL,
            NOW() + interval '2 hours',
            25.50,
            'pending',
            NOW(),
            NOW()
        FROM generate_series(1, 50) AS i;
    """)
    
    duration = time.perf_counter() - start_t
    print(f"[+] Seeded {count:,} records in {duration:.2f}s.")

def benchmark_queries(cur):
    """Benchmark SQL execution speed for Pending Queue & Batch Confirmation."""
    print("\n" + "="*70)
    print(" BENCHMARKING QUERY PERFORMANCE (DATABASE LEVEL)")
    print("="*70)
    
    # 1. Test Pending Dispatch Query (List View)
    q1 = """
        EXPLAIN ANALYZE
        SELECT id, name, planned_weight, state, scheduled_date 
        FROM stock_picking 
        WHERE batch_id IS NULL 
          AND state IN ('waiting', 'confirmed', 'assigned')
          AND picking_type_id = 2
        ORDER BY scheduled_date ASC
        LIMIT 80;
    """
    cur.execute(q1)
    plan_lines = [r[0] for r in cur.fetchall()]
    exec_time_line = [l for l in plan_lines if "Execution Time" in l or "Planning Time" in l]
    print("\n[Query 1] Tải danh sách 'Phiếu chờ sắp xe' (80 dòng đầu):")
    for l in exec_time_line:
        print("  -> " + l)
    
    # 2. Test Concurrency Anti-Collision Check
    cur.execute("SELECT id FROM stock_picking WHERE batch_id IS NULL LIMIT 20;")
    sample_ids = tuple([r[0] for r in cur.fetchall()])
    
    q2 = f"""
        EXPLAIN ANALYZE
        SELECT id, name, batch_id, state 
        FROM stock_picking 
        WHERE id IN {sample_ids} FOR UPDATE;
    """
    cur.execute(q2)
    plan_lines2 = [r[0] for r in cur.fetchall()]
    for l in [l for l in plan_lines2 if "Execution Time" in l]:
        print(f"\n[Query 2] Kiểm tra xung đột & Khóa dòng cho {len(sample_ids)} phiếu chọn (Row Locking):")
        print("  -> " + l)
        
    # 3. Test Bulk Write
    start_t = time.perf_counter()
    cur.execute("INSERT INTO stock_picking_batch (name, state, company_id) VALUES ('PERF-BENCH-BATCH', 'draft', 1) RETURNING id;")
    test_batch_id = cur.fetchone()[0]
    
    cur.execute(f"""
        UPDATE stock_picking 
        SET batch_id = {test_batch_id}, delivery_status = 'assigned'
        WHERE id IN {sample_ids};
    """)
    write_duration = (time.perf_counter() - start_t) * 1000.0
    print(f"\n[Query 3] Gán batch_id cho {len(sample_ids)} phiếu xuất kho (Write + Commit):")
    print(f"  -> Execution Time: {write_duration:.2f} ms")

def cleanup_test_data(cur):
    """Clean up performance test records."""
    print("\n[*] Cleaning up performance test records...")
    cur.execute("DELETE FROM stock_picking WHERE name LIKE 'PERF/%';")
    cur.execute("DELETE FROM stock_picking_batch WHERE name LIKE 'PERF/%' OR name = 'PERF-BENCH-BATCH';")
    print("[+] Test data cleaned successfully.")

def main():
    conn = get_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        ensure_picking_type_flag(cur)
        initial_p, initial_b = count_records(cur)
        print(f"[*] Dữ liệu hiện tại: {initial_p:,} pickings | {initial_b:,} batches")
        
        # Seed 100,000 records sample to benchmark scale
        seed_simulation_data(cur, count=100000)
        conn.commit()
        
        # Run benchmarks
        benchmark_queries(cur)
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print(f"[!] Error: {e}", file=sys.stderr)
        raise
    finally:
        cleanup_test_data(cur)
        conn.commit()
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
