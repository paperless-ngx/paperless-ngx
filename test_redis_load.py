#!/usr/bin/env python3
"""
Redis Load Test Script for Celery Task Queuing
Tests Redis performance with 100 concurrent test tasks
"""

import os
import sys
import time
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
django.setup()

from celery import shared_task, current_app
import redis

@shared_task(name='test_load_task')
def test_load_task(task_num):
    """Simple test task that returns its number"""
    time.sleep(0.1)  # Simulate work
    return f"Task {task_num} completed"

def main():
    print("=== Redis Load Test: 100 Task Queuing ===\n")

    # Get Redis connection info
    from django.conf import settings
    redis_url = settings.CELERY_BROKER_URL
    print(f"Redis URL: {redis_url}")
    print(f"Worker Concurrency: {settings.CELERY_WORKER_CONCURRENCY}")

    # Connect to Redis for monitoring
    r = redis.from_url(redis_url)

    # Get baseline metrics
    print("\n--- Baseline Metrics ---")
    info_before = r.info('stats')
    memory_before = r.info('memory')
    clients_before = r.info('clients')

    print(f"Connected Clients: {clients_before.get('connected_clients', 'N/A')}")
    print(f"Memory Used: {memory_before.get('used_memory_human', 'N/A')}")
    print(f"Total Commands Processed: {info_before.get('total_commands_processed', 'N/A')}")

    # Queue 100 tasks
    print("\n--- Queuing 100 Tasks ---")
    start_time = time.time()
    task_results = []

    for i in range(100):
        result = test_load_task.apply_async(args=[i])
        task_results.append(result)
        if (i + 1) % 10 == 0:
            print(f"Queued {i + 1} tasks...")

    queue_time = time.time() - start_time
    print(f"\n✓ All 100 tasks queued in {queue_time:.3f} seconds")
    print(f"  Average queue time per task: {(queue_time / 100) * 1000:.2f} ms")

    # Get post-queue metrics
    print("\n--- Post-Queue Metrics ---")
    info_after = r.info('stats')
    memory_after = r.info('memory')
    clients_after = r.info('clients')

    print(f"Connected Clients: {clients_after.get('connected_clients', 'N/A')}")
    print(f"Memory Used: {memory_after.get('used_memory_human', 'N/A')}")
    print(f"Total Commands Processed: {info_after.get('total_commands_processed', 'N/A')}")

    # Calculate deltas
    memory_delta = memory_after.get('used_memory', 0) - memory_before.get('used_memory', 0)
    print(f"Memory Delta: {memory_delta / 1024:.2f} KB")

    commands_delta = info_after.get('total_commands_processed', 0) - info_before.get('total_commands_processed', 0)
    print(f"Commands Processed: {commands_delta}")

    # Check task completion
    print("\n--- Checking Task Completion (30s timeout) ---")
    completed = 0
    failed = 0
    pending = 0
    timeout = 30
    check_start = time.time()

    while time.time() - check_start < timeout:
        completed = sum(1 for r in task_results if r.ready() and r.successful())
        failed = sum(1 for r in task_results if r.ready() and r.failed())
        pending = sum(1 for r in task_results if not r.ready())

        if pending == 0:
            break

        time.sleep(1)

    total_time = time.time() - start_time

    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    print(f"Pending: {pending}")
    print(f"Total Time: {total_time:.2f} seconds")

    if completed > 0:
        print(f"Throughput: {completed / total_time:.2f} tasks/sec")

    # Final Redis metrics
    print("\n--- Final Redis Metrics ---")
    info_final = r.info('stats')
    memory_final = r.info('memory')

    print(f"Peak Memory Used: {memory_final.get('used_memory_peak_human', 'N/A')}")
    print(f"Total Connections Received: {info_final.get('total_connections_received', 'N/A')}")
    print(f"Rejected Connections: {info_final.get('rejected_connections', 'N/A')}")

    print("\n✓ Load test completed")

if __name__ == '__main__':
    main()
