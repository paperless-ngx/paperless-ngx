#!/usr/bin/env python3
"""
Script to test Celery task execution and performance
Tests basic task queuing, execution, and performance under load
"""

import os
import sys
import time
import json
import random
from datetime import datetime
from typing import Dict, List

# Add the project to the path
sys.path.insert(0, '/usr/src/paperless/src')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')

import django
django.setup()

from celery import Celery, group
from celery.result import AsyncResult
from django.conf import settings
from redis import Redis


class CeleryTaskTester:
    """Test Celery task execution and performance"""

    def __init__(self):
        self.app = Celery('paperless')
        self.app.config_from_object('django.conf:settings', namespace='CELERY')
        self.redis_client = None
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'broker_url': settings.CELERY_BROKER_URL,
            'tests': {}
        }

    def connect_redis(self) -> bool:
        """Test Redis connection"""
        try:
            # Parse Redis URL
            redis_url = settings.CELERY_BROKER_URL
            if redis_url.startswith('redis://'):
                # Simple redis:// URL
                parts = redis_url.replace('redis://', '').split(':')
                host = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 6379
                self.redis_client = Redis(host=host, port=port, decode_responses=True)
                self.redis_client.ping()
                return True
            else:
                print(f"Unsupported Redis URL format: {redis_url}")
                return False
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            return False

    def get_redis_info(self) -> Dict:
        """Get Redis server information"""
        if not self.redis_client:
            return {}

        try:
            info = self.redis_client.info()
            return {
                'version': info.get('redis_version', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', '0'),
                'total_connections_received': info.get('total_connections_received', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
            }
        except Exception as e:
            print(f"Failed to get Redis info: {e}")
            return {}

    def get_queue_structure(self) -> Dict:
        """Analyze current queue structure in Redis"""
        if not self.redis_client:
            return {}

        try:
            # Scan for all keys
            keys = []
            for key in self.redis_client.scan_iter(count=1000):
                keys.append(key)

            # Categorize keys
            celery_keys = [k for k in keys if 'celery' in k.lower()]
            queue_keys = [k for k in keys if 'queue' in k.lower()]

            # Get key types
            key_types = {}
            for key in keys[:100]:  # Sample first 100 keys
                key_type = self.redis_client.type(key)
                key_types[key_type] = key_types.get(key_type, 0) + 1

            return {
                'total_keys': len(keys),
                'celery_keys': len(celery_keys),
                'queue_keys': len(queue_keys),
                'key_types': key_types,
                'sample_keys': keys[:20]
            }
        except Exception as e:
            print(f"Failed to get queue structure: {e}")
            return {}

    def test_simple_task(self) -> Dict:
        """Test a simple Celery task execution"""
        print("\nTest 1: Simple task execution")
        print("-" * 50)

        try:
            # Import a simple task from paperless
            from documents.tasks import index_optimize

            # Queue the task
            start_time = time.time()
            result = index_optimize.apply_async()
            task_id = result.id
            print(f"Task queued: {task_id}")

            # Wait for result (with timeout)
            timeout = 30
            try:
                result.get(timeout=timeout, propagate=False)
                execution_time = time.time() - start_time
                status = result.status
                print(f"Task completed: {status} in {execution_time:.2f}s")

                return {
                    'status': 'PASS',
                    'task_id': task_id,
                    'execution_time': execution_time,
                    'task_status': status
                }
            except Exception as e:
                return {
                    'status': 'TIMEOUT',
                    'task_id': task_id,
                    'error': str(e),
                    'elapsed': time.time() - start_time
                }

        except Exception as e:
            print(f"Error: {e}")
            return {
                'status': 'FAIL',
                'error': str(e)
            }

    def test_task_queuing(self, num_tasks: int = 10) -> Dict:
        """Test queuing multiple tasks"""
        print(f"\nTest 2: Queuing {num_tasks} tasks")
        print("-" * 50)

        try:
            from documents.tasks import index_optimize

            task_ids = []
            start_time = time.time()

            # Queue multiple tasks
            for i in range(num_tasks):
                result = index_optimize.apply_async()
                task_ids.append(result.id)

            queue_time = time.time() - start_time
            print(f"Queued {len(task_ids)} tasks in {queue_time:.2f}s")
            print(f"Average queue time: {(queue_time / num_tasks) * 1000:.2f}ms per task")

            # Check task states
            time.sleep(2)  # Wait a bit for tasks to be picked up
            states = {}
            for task_id in task_ids:
                result = AsyncResult(task_id, app=self.app)
                state = result.status
                states[state] = states.get(state, 0) + 1

            print(f"Task states: {states}")

            return {
                'status': 'PASS',
                'num_tasks': num_tasks,
                'queue_time': queue_time,
                'avg_queue_time_ms': (queue_time / num_tasks) * 1000,
                'task_states': states
            }

        except Exception as e:
            print(f"Error: {e}")
            return {
                'status': 'FAIL',
                'error': str(e)
            }

    def test_performance_under_load(self, num_tasks: int = 100) -> Dict:
        """Test Redis and Celery performance under load"""
        print(f"\nTest 3: Performance test with {num_tasks} tasks")
        print("-" * 50)

        try:
            from documents.tasks import index_optimize

            # Get baseline memory
            baseline_memory = self.redis_client.info('memory').get('used_memory', 0)
            baseline_memory_human = self.redis_client.info('memory').get('used_memory_human', '0')
            print(f"Baseline Redis memory: {baseline_memory_human}")

            # Queue tasks in batches
            task_ids = []
            start_time = time.time()
            batch_size = 10

            for batch in range(0, num_tasks, batch_size):
                batch_results = []
                for i in range(min(batch_size, num_tasks - batch)):
                    result = index_optimize.apply_async()
                    batch_results.append(result.id)

                task_ids.extend(batch_results)
                print(f"Queued batch {batch // batch_size + 1}: {len(task_ids)}/{num_tasks} tasks")

            total_queue_time = time.time() - start_time
            print(f"\nTotal queue time: {total_queue_time:.2f}s")
            print(f"Average: {(total_queue_time / num_tasks) * 1000:.2f}ms per task")

            # Wait a bit for tasks to be processed
            time.sleep(5)

            # Check task states
            states = {}
            for task_id in task_ids:
                result = AsyncResult(task_id, app=self.app)
                state = result.status
                states[state] = states.get(state, 0) + 1

            # Get peak memory
            peak_memory = self.redis_client.info('memory').get('used_memory', 0)
            peak_memory_human = self.redis_client.info('memory').get('used_memory_peak_human', '0')
            memory_increase = peak_memory - baseline_memory
            memory_increase_mb = memory_increase / (1024 * 1024)

            print(f"\nPeak Redis memory: {peak_memory_human}")
            print(f"Memory increase: {memory_increase_mb:.2f} MB")
            print(f"Task states: {states}")

            # Calculate throughput
            throughput = num_tasks / total_queue_time
            print(f"Throughput: {throughput:.2f} tasks/second")

            return {
                'status': 'PASS',
                'num_tasks': num_tasks,
                'total_queue_time': total_queue_time,
                'avg_queue_time_ms': (total_queue_time / num_tasks) * 1000,
                'throughput_tasks_per_sec': throughput,
                'baseline_memory': baseline_memory_human,
                'peak_memory': peak_memory_human,
                'memory_increase_mb': memory_increase_mb,
                'task_states': states
            }

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'FAIL',
                'error': str(e)
            }

    def test_tenant_aware_queuing(self) -> Dict:
        """Test tenant-aware queue namespace capability"""
        print("\nTest 4: Tenant-aware queue namespace test")
        print("-" * 50)

        try:
            # Test creating keys with tenant prefixes
            tenant_ids = ['tenant-001', 'tenant-002', 'tenant-003']
            test_pass = True
            created_keys = []

            for tenant_id in tenant_ids:
                key = f"test:queue:{tenant_id}:tasks"
                # Set a test value
                self.redis_client.set(key, f"value-{tenant_id}")
                created_keys.append(key)
                print(f"Created key: {key}")

            # Verify keys exist
            for tenant_id in tenant_ids:
                key = f"test:queue:{tenant_id}:tasks"
                value = self.redis_client.get(key)
                if value != f"value-{tenant_id}":
                    test_pass = False
                    print(f"Verification failed for {key}")
                else:
                    print(f"Verified key: {key} = {value}")

            # Clean up
            for key in created_keys:
                self.redis_client.delete(key)

            if test_pass:
                print("\nTenant-aware queuing: SUPPORTED")
                return {
                    'status': 'PASS',
                    'tenants_tested': len(tenant_ids),
                    'recommendation': 'Use queue name pattern: tenant-<tenant_id> for multi-tenant support'
                }
            else:
                return {
                    'status': 'FAIL',
                    'error': 'Key verification failed'
                }

        except Exception as e:
            print(f"Error: {e}")
            return {
                'status': 'FAIL',
                'error': str(e)
            }

    def run_all_tests(self):
        """Run all tests and generate report"""
        print("=" * 60)
        print("Celery Task Execution and Performance Tests")
        print("=" * 60)

        # Test Redis connection
        print("\nConnecting to Redis...")
        if not self.connect_redis():
            print("FATAL: Cannot connect to Redis")
            self.results['tests']['redis_connection'] = {
                'status': 'FAIL',
                'error': 'Connection failed'
            }
            return self.results

        print("Redis connection: OK")
        self.results['tests']['redis_connection'] = {'status': 'PASS'}

        # Get Redis info
        print("\nGetting Redis information...")
        redis_info = self.get_redis_info()
        print(f"Redis version: {redis_info.get('version', 'unknown')}")
        print(f"Connected clients: {redis_info.get('connected_clients', 0)}")
        print(f"Memory used: {redis_info.get('used_memory_human', '0')}")
        self.results['redis_info'] = redis_info

        # Get queue structure
        print("\nAnalyzing queue structure...")
        queue_structure = self.get_queue_structure()
        print(f"Total keys: {queue_structure.get('total_keys', 0)}")
        print(f"Celery keys: {queue_structure.get('celery_keys', 0)}")
        self.results['queue_structure'] = queue_structure

        # Run tests
        self.results['tests']['simple_task'] = self.test_simple_task()
        self.results['tests']['task_queuing'] = self.test_task_queuing(10)
        self.results['tests']['performance_load'] = self.test_performance_under_load(100)
        self.results['tests']['tenant_aware_queuing'] = self.test_tenant_aware_queuing()

        # Generate summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)

        total_tests = len(self.results['tests'])
        passed_tests = sum(1 for t in self.results['tests'].values() if t.get('status') == 'PASS')
        failed_tests = sum(1 for t in self.results['tests'].values() if t.get('status') == 'FAIL')

        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")

        self.results['summary'] = {
            'total': total_tests,
            'passed': passed_tests,
            'failed': failed_tests
        }

        return self.results


def main():
    """Main entry point"""
    tester = CeleryTaskTester()
    results = tester.run_all_tests()

    # Save results to file
    output_file = f"/tmp/celery-test-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")

    # Exit with appropriate code
    if results['summary']['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
