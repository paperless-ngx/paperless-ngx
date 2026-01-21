---
sidebar_position: 8
title: Multi-Tenant Celery Tasks Guide
description: Implement and manage Celery background tasks in multi-tenant Paperless deployments
---

# Multi-Tenant Celery Tasks Guide

This guide explains how to implement, execute, and troubleshoot Celery background tasks in Paperless-ngx multi-tenant environments.

## Overview

Celery provides asynchronous task processing for long-running operations like document consumption, OCR, classifier training, and scheduled workflows. In multi-tenant deployments, **tenant context isolation** ensures tasks only access data from their designated tenant.

### Key Concepts

- **Tenant Context**: Per-request context (thread-local storage + PostgreSQL RLS) identifying the current tenant
- **restore_tenant_context()**: Helper function that restores tenant context in task workers
- **Scheduled Tasks**: Global scheduler (Celery Beat) that spawns per-tenant tasks
- **Rate Limiting**: Batched task spawning with configurable delays to prevent worker overload
- **Tenant Isolation**: Row-Level Security (RLS) queries and thread-local storage prevent cross-tenant data leaks

:::info Rate Limiting in Multi-Tenant Deployments

For deployments with many tenants (100+), **rate limiting is essential** to prevent worker overload. The `spawn_tenant_tasks_with_rate_limiting()` helper automatically batches task spawning based on configuration:

```bash
# Spawn 10 tasks per batch, wait 60 seconds between batches
CELERY_TENANT_BATCH_SIZE=10
CELERY_TENANT_BATCH_DELAY=60
```

All wrapper tasks in Paperless use this pattern by default. See [Rate Limiting Configuration](#rate-limiting-configuration) for details.

:::

## Tenant Context Restoration Pattern

### The Problem

Celery workers receive tasks from the message queue without HTTP context. Unlike web requests, tasks don't have `request.tenant_id` available. Without explicit context restoration, database queries run without tenant filtering, causing data leaks or crashes.

### The Solution: `restore_tenant_context()`

The `restore_tenant_context()` helper function restores both the thread-local storage and PostgreSQL RLS context:

```python
def restore_tenant_context(tenant_id: str | uuid.UUID | None):
    """
    Restore tenant context for Celery tasks.

    Sets:
    - Thread-local storage via set_current_tenant_id()
    - PostgreSQL RLS session variable: SET app.current_tenant

    Args:
        tenant_id: UUID (string or UUID object) of the tenant. Can be None.
    """
    if tenant_id is None:
        logger.warning("restore_tenant_context called with tenant_id=None")
        return

    from django.db import connection
    from documents.models import set_current_tenant_id

    tenant_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    set_current_tenant_id(tenant_uuid)

    with connection.cursor() as cursor:
        cursor.execute("SET app.current_tenant = %s", [str(tenant_uuid)])

    logger.debug(f"Restored tenant context: {tenant_uuid}")
```

### How It Works

1. **Accepts flexible input**: Takes `tenant_id` as string, UUID object, or None
2. **Sets thread-local storage**: Calls `set_current_tenant_id()` for Django's context
3. **Configures PostgreSQL RLS**: Executes `SET app.current_tenant` to activate row-level security
4. **Logs for debugging**: Records context restoration for troubleshooting

### Implementation

Every task that accesses tenant-scoped data must call `restore_tenant_context()` at the start:

```python
@shared_task
def train_classifier(*, scheduled=True, tenant_id=None):
    # Restore tenant context FIRST
    restore_tenant_context(tenant_id)

    # Now all queries are automatically filtered by tenant
    classifiers = DocumentClassifier.objects.all()  # Only current tenant
    ...
```

## When to Add tenant_id Parameter

### Rule: All Tenant-Scoped Tasks Need tenant_id

Add a `tenant_id` parameter to any task that:

- **Queries tenant-scoped models** (Document, Tag, Correspondent, etc.)
- **Updates or deletes tenant data**
- **Accesses tenant media directories** (e.g., `MEDIA_ROOT/tenant_<id>/`)
- **Interacts with tenant-specific indexes** (e.g., Whoosh search index)

### Examples of Tasks That Need tenant_id

```python
# ✅ NEEDS tenant_id - accesses Document model
@shared_task
def train_classifier(*, scheduled=True, tenant_id=None):
    restore_tenant_context(tenant_id)
    tags_with_auto_matching = Tag.objects.filter(matching_algorithm=Tag.MATCH_AUTO)
    ...

# ✅ NEEDS tenant_id - modifies documents
@shared_task
def bulk_update_documents(document_ids, tenant_id=None):
    restore_tenant_context(tenant_id)
    documents = Document.objects.filter(id__in=document_ids)
    ...

# ✅ NEEDS tenant_id - processes files
@shared_task
def consume_file(self: Task, input_doc, overrides=None, tenant_id=None):
    restore_tenant_context(tenant_id)
    # Create documents, index, etc.
    ...
```

### Examples of Tasks That DON'T Need tenant_id

```python
# ✅ NO tenant_id needed - global operation
@shared_task
def index_optimize(tenant_id=None):
    # Index optimization affects all tenants uniformly
    # tenant_id parameter accepted for consistency but ignored
    ix = index.open_index()
    writer = AsyncWriter(ix)
    writer.commit(optimize=True)
```

### Parameter Signature

Always use this pattern for task parameters:

```python
@shared_task
def my_task(arg1, arg2, *, scheduled=True, tenant_id=None):
    restore_tenant_context(tenant_id)
    # Task logic here
    ...
```

- **Positional parameters first** (arg1, arg2)
- **Keyword-only parameters** (use `*`) for options
- **tenant_id last** as optional keyword parameter
- **Never make tenant_id required** - allows execution from HTTP context

## Wrapper Task Pattern for Scheduled Execution

### The Problem

Celery Beat runs tasks on a schedule (e.g., daily, weekly). In multi-tenant setups, a single scheduled task can't execute per-tenant automatically—it needs a wrapper to spawn per-tenant tasks.

**Additional Challenge**: Spawning tasks for many tenants simultaneously can overload Celery workers, causing task backlog and delays. The solution is **rate limiting** with staggered task execution.

### The Solution: Wrapper Tasks with Rate Limiting

Create a "wrapper" task that:
1. Fetches all active tenants
2. Spawns per-tenant tasks in **batches** with optional **delays** between batches
3. Prevents worker overload in multi-tenant deployments with 100+ tenants

### Implementation Pattern

Modern implementation uses the `spawn_tenant_tasks_with_rate_limiting()` helper:

```python
@shared_task
def scheduled_train_classifier_all_tenants():
    """
    Wrapper for Celery Beat: Trains classifier for all active tenants.
    Spawns per-tenant tasks with rate limiting to prevent worker overload.
    """
    from paperless.models import Tenant

    tenants = Tenant.objects.filter(is_active=True)
    spawn_tenant_tasks_with_rate_limiting(
        tenants=tenants,
        task_callable=train_classifier.delay,
        task_name="train_classifier",
        scheduled=True,
    )
```

### Legacy Implementation (Still Supported)

For backwards compatibility, you can still implement wrapper tasks without rate limiting:

```python
@shared_task
def scheduled_train_classifier_all_tenants():
    """Wrapper for Celery Beat: Trains classifier for all active tenants."""
    from paperless.models import Tenant

    tenants = Tenant.objects.filter(is_active=True)
    logger.info(f"Running scheduled train_classifier for {tenants.count()} active tenants")

    for tenant in tenants:
        logger.info(f"Spawning train_classifier for tenant: {tenant.subdomain} ({tenant.id})")
        train_classifier.delay(scheduled=True, tenant_id=str(tenant.id))
```

However, **rate limiting is strongly recommended** for deployments with many tenants.

### Rate Limiting Configuration

Rate limiting is controlled by Django settings:

```python
# In settings.py or environment variables:

# CELERY_TENANT_BATCH_SIZE: Number of tasks to spawn per batch (default: 10)
#   - 0 or 1: Spawn all tasks immediately (legacy behavior, not recommended)
#   - 10: Spawn in batches of 10 tasks
#   - 25: Spawn in batches of 25 tasks
CELERY_TENANT_BATCH_SIZE = 10

# CELERY_TENANT_BATCH_DELAY: Delay in seconds between batches (default: 60)
#   - 0: No delay between batches
#   - 60: Wait 60 seconds between batches (default, recommended)
CELERY_TENANT_BATCH_DELAY = 60
```

#### Environment Variables

Set rate limiting via environment variables (recommended for Docker/Kubernetes):

```bash
# Spawn 10 tasks, wait 60 seconds between batches
CELERY_TENANT_BATCH_SIZE=10
CELERY_TENANT_BATCH_DELAY=60
```

#### When to Adjust Settings

| Deployment Size | Batch Size | Batch Delay | Rationale |
|----------|-----------|------------|-----------|
| Tiny (under 10 tenants) | 0 | 0 | Spawn all immediately, no overload risk |
| Small (10-50 tenants) | 10 | 30 | Moderate batching, minimal delay |
| Medium (50-100 tenants) | 15 | 45 | Conservative batching for safety |
| Large (100+ tenants) | 20-25 | 60 | Aggressive rate limiting to prevent overload |
| Worker limited | 5 | 120 | Very conservative, 2-minute delays |

### spawn_tenant_tasks_with_rate_limiting() Helper

This helper function automates rate-limited task spawning:

```python
def spawn_tenant_tasks_with_rate_limiting(tenants, task_callable, task_name, **task_kwargs):
    """
    Spawns tenant-specific tasks with rate limiting/staggered execution.

    Args:
        tenants: QuerySet of Tenant objects
        task_callable: The Celery task to spawn (e.g., train_classifier.delay)
        task_name: Human-readable task name for logging
        **task_kwargs: Additional keyword arguments to pass to the task (excluding tenant_id)

    Rate limiting is controlled by:
        - CELERY_TENANT_BATCH_SIZE: Number of tasks to spawn per batch (0 = no batching)
        - CELERY_TENANT_BATCH_DELAY: Delay in seconds between batches (0 = no delay)
    """
```

**Example Usage**:

```python
@shared_task
def scheduled_my_task_all_tenants():
    """Spawn per-tenant tasks with rate limiting."""
    from paperless.models import Tenant

    tenants = Tenant.objects.filter(is_active=True)
    spawn_tenant_tasks_with_rate_limiting(
        tenants=tenants,
        task_callable=my_task.delay,
        task_name="my_task",
        param1="value",  # Additional kwargs are passed to the task
    )
```

### Key Points

- **Called by Celery Beat**: Configure in `celery.py` beat schedule
- **No restore_tenant_context()**: Wrapper runs in scheduler context (no tenant needed)
- **Spawns per-tenant tasks**: Uses `.delay()` to queue per-tenant work
- **Rate limiting included**: Automatically batches tasks based on settings
- **Converts UUID to string**: Pass `str(tenant.id)` to tasks automatically
- **Logs batch progress**: Tracks batch numbers and tenant counts
- **Respects delays**: Pauses between batches to prevent worker overload

### Celery Beat Configuration

In your `celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'train-classifier-all-tenants': {
        'task': 'documents.tasks.scheduled_train_classifier_all_tenants',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
    },
    'sanity-check-all-tenants': {
        'task': 'documents.tasks.scheduled_sanity_check_all_tenants',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM
    },
    'llmindex-index-all-tenants': {
        'task': 'documents.tasks.scheduled_llmindex_index_all_tenants',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4:00 AM
    },
    'empty-trash-all-tenants': {
        'task': 'documents.tasks.scheduled_empty_trash_all_tenants',
        'schedule': crontab(hour=5, minute=0),  # Daily at 5:00 AM
    },
    'check-workflows-all-tenants': {
        'task': 'documents.tasks.scheduled_check_workflows_all_tenants',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6:00 AM
    },
}
```

**Rate limiting applies to all wrapper tasks automatically.** Configure via environment variables:

```bash
CELERY_TENANT_BATCH_SIZE=10
CELERY_TENANT_BATCH_DELAY=60
```

### Existing Wrapper Tasks

Paperless provides these wrapper tasks. All use rate limiting via `spawn_tenant_tasks_with_rate_limiting()`:

| Wrapper Task | Spawned Task | Purpose | Rate Limited |
|---|---|---|---|
| `scheduled_train_classifier_all_tenants` | `train_classifier` | Train auto-matching classifier | ✅ Yes |
| `scheduled_sanity_check_all_tenants` | `sanity_check` | Validate system configuration | ✅ Yes |
| `scheduled_llmindex_index_all_tenants` | `llmindex_index` | Update LLM vector index | ✅ Yes |
| `scheduled_empty_trash_all_tenants` | `empty_trash` | Purge deleted documents | ✅ Yes |
| `scheduled_check_workflows_all_tenants` | `check_scheduled_workflows` | Execute scheduled workflows | ✅ Yes |

## Adding New Tasks: Step-by-Step

### Step 1: Define the Per-Tenant Task

```python
@shared_task
def my_new_task(param1, *, tenant_id=None):
    """
    Brief description of what the task does.

    Args:
        param1: Description of required parameter
        tenant_id: UUID of the tenant (string or UUID object)
    """
    # Always restore context first
    restore_tenant_context(tenant_id)

    # Now your task logic - queries are auto-filtered by tenant
    documents = Document.objects.all()  # Only from current tenant
    ...
```

### Step 2: If Task Runs on Schedule, Create Wrapper

Use rate limiting via `spawn_tenant_tasks_with_rate_limiting()`:

```python
@shared_task
def scheduled_my_new_task_all_tenants():
    """
    Wrapper for Celery Beat: Runs my_new_task for all active tenants.
    Spawns per-tenant tasks with rate limiting to prevent worker overload.
    """
    from paperless.models import Tenant
    from documents.tasks import spawn_tenant_tasks_with_rate_limiting

    tenants = Tenant.objects.filter(is_active=True)
    spawn_tenant_tasks_with_rate_limiting(
        tenants=tenants,
        task_callable=my_new_task.delay,
        task_name="my_new_task",
        param1="value",  # Additional parameters passed to the task
    )
```

**Legacy Implementation** (not recommended for many tenants):

```python
@shared_task
def scheduled_my_new_task_all_tenants():
    """Wrapper for Celery Beat: Runs my_new_task for all active tenants."""
    from paperless.models import Tenant

    tenants = Tenant.objects.filter(is_active=True)
    logger.info(f"Running scheduled my_new_task for {tenants.count()} active tenants")

    for tenant in tenants:
        logger.info(f"Spawning my_new_task for tenant: {tenant.subdomain} ({tenant.id})")
        my_new_task.delay(param1="value", tenant_id=str(tenant.id))
```

### Step 3: Register in Celery Beat (if scheduled)

```python
app.conf.beat_schedule = {
    'my-new-task-all-tenants': {
        'task': 'documents.tasks.scheduled_my_new_task_all_tenants',
        'schedule': crontab(hour=4, minute=0),  # Configure as needed
    },
}
```

### Step 4: Call from HTTP Endpoints

```python
# In views.py or serializers
from documents.models import get_current_tenant_id
from documents.tasks import my_new_task

tenant_id = get_current_tenant_id()
my_new_task.delay(param1="value", tenant_id=str(tenant_id) if tenant_id else None)
```

### Step 5: Write Tests

```python
from django.test import TestCase
from documents import tasks
from paperless.models import Tenant

class MyNewTaskTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            subdomain='test-tenant',
            name='Test Tenant',
            region='us',
            is_active=True,
        )

    def test_my_new_task_restores_context(self):
        """Verify task restores tenant context."""
        from documents.models import get_current_tenant_id, set_current_tenant_id

        # Clear context
        set_current_tenant_id(None)

        # Call task
        tasks.my_new_task('test_value', tenant_id=str(self.tenant.id))

        # Verify context was restored
        self.assertEqual(get_current_tenant_id(), self.tenant.id)

    def test_scheduled_wrapper_spawns_per_tenant(self):
        """Verify wrapper task spawns per-tenant tasks."""
        with patch('documents.tasks.my_new_task.delay') as mock_delay:
            tasks.scheduled_my_new_task_all_tenants()

            # Should be called once per active tenant
            mock_delay.assert_called_once()
            call_args = mock_delay.call_args
            self.assertEqual(call_args.kwargs['tenant_id'], str(self.tenant.id))
```

## API Endpoint: /api/tasks/run/

### Overview

The `/api/tasks/run/` endpoint allows superusers to manually trigger tasks.

### Endpoint Details

**URL**: `POST /api/tasks/run/`

**Authentication**: Required (superuser only)

**Request Body**:
```json
{
    "task_name": "TRAIN_CLASSIFIER"
}
```

**Response**:
```json
{
    "result": "celery-task-uuid"
}
```

### Supported Tasks

| Task Name | Task Function | Purpose |
|---|---|---|
| `INDEX_OPTIMIZE` | `index_optimize()` | Optimize Whoosh search index |
| `TRAIN_CLASSIFIER` | `train_classifier(scheduled=False)` | Train auto-matching classifier |
| `CHECK_SANITY` | `sanity_check(scheduled=False, raise_on_error=False)` | Run system sanity checks |
| `LLMINDEX_UPDATE` | `llmindex_index(scheduled=False, rebuild=False)` | Update LLM vector index |

### Tenant Context in API

The endpoint automatically includes tenant context from the HTTP request:

```python
@action(methods=["post"], detail=False)
def run(self, request):
    serializer = RunTaskViewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    task_name = serializer.validated_data.get("task_name")

    if not request.user.is_superuser:
        return HttpResponseForbidden("Insufficient permissions")

    try:
        task_func, task_args = self.TASK_AND_ARGS_BY_NAME[task_name]

        # Add tenant_id from request context
        tenant_id = getattr(request, 'tenant_id', None)
        if tenant_id:
            task_args = {**task_args, 'tenant_id': str(tenant_id)}

        # Execute asynchronously through Celery
        result = task_func.delay(**task_args)

        return Response({"result": str(result)})
    except Exception as e:
        logger.warning(f"An error occurred running task: {e!s}")
        return HttpResponseServerError(...)
```

### Using the Endpoint

**Command Line Example**:
```bash
curl -X POST http://localhost:8000/api/tasks/run/ \
  -H "Authorization: Token YOUR_SUPERUSER_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant-uuid" \
  -d '{"task_name": "TRAIN_CLASSIFIER"}'
```

**Python Example**:
```python
import requests

response = requests.post(
    'http://localhost:8000/api/tasks/run/',
    headers={
        'Authorization': 'Token your_token',
        'X-Tenant-ID': 'your-tenant-id',
    },
    json={'task_name': 'TRAIN_CLASSIFIER'},
)

task_uuid = response.json()['result']
print(f"Task queued: {task_uuid}")
```

### Tenant-Aware Execution

When a superuser calls `/api/tasks/run/`, the endpoint:
1. Reads `request.tenant_id` from middleware/request context
2. Includes it in the task call: `task_func.delay(..., tenant_id=str(tenant_id))`
3. Task worker receives tenant_id and calls `restore_tenant_context(tenant_id)`
4. All database queries are filtered to that tenant

**Important**: The tenant context comes from the HTTP request headers (typically `X-Tenant-ID` set by middleware). Multi-tenant deployments must ensure proper middleware configuration.

## Scheduled Tasks: Per-Tenant vs Global Execution

### Global Tasks (Rarely Needed)

Some tasks run globally and affect all tenants uniformly:

```python
@shared_task
def index_optimize(tenant_id=None):
    # Index optimization is a global operation
    # The tenant_id parameter is accepted for API consistency but not used
    ix = index.open_index()
    writer = AsyncWriter(ix)
    writer.commit(optimize=True)
```

**When to use**:
- Operations that must run once across all tenants
- Infrastructure maintenance (cache warming, cleanup)
- System-wide optimizations

### Per-Tenant Tasks (Standard Pattern)

Most tasks should execute per-tenant:

```python
@shared_task
def train_classifier(*, scheduled=True, tenant_id=None):
    restore_tenant_context(tenant_id)
    # Each tenant trains their own classifier
    if not Tag.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists():
        return "No automatic matching items"
    # ... training logic ...
```

**When to use**:
- Tasks that process tenant-specific data
- Operations that must be isolated per-tenant
- Standard scheduled maintenance tasks

### Implementation Difference

**Global Execution**:
```python
# In celery.py
app.conf.beat_schedule = {
    'global-task': {
        'task': 'app.tasks.global_task',
        'schedule': crontab(hour=0, minute=0),
    },
}
```

**Per-Tenant Execution**:
```python
# In celery.py
app.conf.beat_schedule = {
    'per-tenant-task': {
        'task': 'app.tasks.scheduled_per_tenant_task_all_tenants',
        'schedule': crontab(hour=0, minute=0),
    },
}

# In tasks.py
@shared_task
def scheduled_per_tenant_task_all_tenants():
    """Spawn per-tenant tasks"""
    for tenant in Tenant.objects.filter(is_active=True):
        per_tenant_task.delay(tenant_id=str(tenant.id))
```

## Rate Limiting Troubleshooting

### Problem: Worker Queue Growing Too Fast

**Symptom**: Celery worker queue backs up, tasks take too long to complete.

**Cause**: Too many tasks spawned simultaneously for large tenant counts (100+ tenants).

**Solution**: Adjust rate limiting settings:

```bash
# Reduce batch size for more conservative rate limiting
CELERY_TENANT_BATCH_SIZE=5
CELERY_TENANT_BATCH_DELAY=120

# Or increase delay between batches
CELERY_TENANT_BATCH_SIZE=10
CELERY_TENANT_BATCH_DELAY=120
```

**Monitoring**: Check Celery worker queue length:

```bash
celery -A paperless inspect active_queues
celery -A paperless inspect reserved
```

### Problem: Wrapper Task Takes Too Long

**Symptom**: Scheduled tasks finish much later than their scheduled time.

**Cause**: Rate limiting delays accumulate with many tenants. For example:
- 120 tenants ÷ 10 per batch = 12 batches
- 12 batches × 60-second delay = 660 seconds (11 minutes)

**Solution**:
1. Increase batch size if workers can handle it:
   ```bash
   CELERY_TENANT_BATCH_SIZE=20
   ```

2. Reduce delay if tasks are quick:
   ```bash
   CELERY_TENANT_BATCH_DELAY=30
   ```

3. Schedule wrapper tasks further apart:
   ```python
   app.conf.beat_schedule = {
       'train-classifier': {
           'task': 'documents.tasks.scheduled_train_classifier_all_tenants',
           'schedule': crontab(hour=1, minute=0),  # 1:00 AM instead of 2:00 AM
       },
   }
   ```

### Problem: Batching Doesn't Work

**Symptom**: Tasks spawn all at once despite batch settings.

**Cause**: `CELERY_TENANT_BATCH_SIZE` set to 0 or 1 (legacy behavior).

**Solution**: Set appropriate batch size:

```bash
# ❌ Wrong - spawns all immediately
CELERY_TENANT_BATCH_SIZE=0

# ✅ Correct - batches in groups of 10
CELERY_TENANT_BATCH_SIZE=10
```

## Troubleshooting

### Error: "tenant_id cannot be None"

**Cause**: A task that requires tenant context was called without providing `tenant_id`.

**Solution**:
1. Check the task call includes `tenant_id`:
   ```python
   # ✅ CORRECT
   my_task.delay(tenant_id=str(tenant_id))

   # ❌ WRONG
   my_task.delay()
   ```

2. Verify `restore_tenant_context()` is called in the task:
   ```python
   @shared_task
   def my_task(*, tenant_id=None):
       restore_tenant_context(tenant_id)  # ← Must be here
       ...
   ```

3. If calling from HTTP view, ensure tenant_id is available:
   ```python
   from documents.models import get_current_tenant_id

   tenant_id = get_current_tenant_id()
   if not tenant_id:
       raise ValueError("No tenant context available")
   my_task.delay(tenant_id=str(tenant_id))
   ```

### Error: "No active tenants found"

**Cause**: Wrapper task found no active tenants to spawn per-tenant tasks.

**Solution**:
1. Verify tenant exists in database:
   ```bash
   python manage.py shell
   >>> from paperless.models import Tenant
   >>> Tenant.objects.filter(is_active=True).count()
   ```

2. Check Celery logs for the wrapper task execution
3. Consider setting `is_active=True` if tenant is disabled:
   ```bash
   python manage.py shell
   >>> tenant = Tenant.objects.get(subdomain='my-tenant')
   >>> tenant.is_active = True
   >>> tenant.save()
   ```

### Error: "Row-level security policy error"

**Cause**: Tenant context wasn't properly restored in the task.

**Solution**:
1. Verify `restore_tenant_context()` was called before any queries
2. Check that `tenant_id` was passed to the task:
   ```python
   # In task definition
   @shared_task
   def my_task(*, tenant_id=None):
       restore_tenant_context(tenant_id)  # Must be first
       Document.objects.filter(...)  # Now safe
   ```

3. Verify PostgreSQL RLS is enabled:
   ```sql
   SELECT * FROM pg_policies WHERE tablename LIKE 'documents_%';
   ```

### Task Hangs or Never Completes

**Cause**:
- Celery worker not running
- Database connection issues
- Infinite loops in task logic

**Solution**:
1. Check Celery worker status:
   ```bash
   celery -A paperless inspect active
   celery -A paperless inspect stats
   ```

2. Check Redis connection:
   ```bash
   redis-cli PING
   redis-cli INFO
   ```

3. Review task logs:
   ```bash
   tail -f /var/log/paperless/celery.log
   ```

4. Check database connectivity and RLS policies:
   ```sql
   SELECT * FROM pg_stat_activity WHERE datname = 'paperless';
   ```

### Task Lost Without Error

**Cause**:
- Worker crashed without logging error
- Broker connection lost
- Result backend issue

**Solution**:
1. Enable task result tracking:
   ```python
   # In celery.py
   app.conf.task_track_started = True
   app.conf.result_extended = True
   ```

2. Check broker status:
   ```bash
   redis-cli KEYS "celery*"
   ```

3. Review worker logs for crashes:
   ```bash
   journalctl -u celery-worker -n 100
   ```

## Best Practices

1. **Always pass tenant_id**:
   ```python
   # ✅ Good - always include tenant_id
   task.delay(arg1=value, tenant_id=str(tenant_id))

   # ❌ Bad - missing tenant_id
   task.delay(arg1=value)
   ```

2. **Restore context first**:
   ```python
   @shared_task
   def my_task(*, tenant_id=None):
       restore_tenant_context(tenant_id)  # Must be first line
       # ... rest of task logic
   ```

3. **Use string for tenant_id in .delay()**:
   ```python
   # ✅ Correct - UUID as string
   task.delay(tenant_id=str(tenant_uuid))

   # ❌ Wrong - UUID objects don't serialize to JSON
   task.delay(tenant_id=tenant_uuid)
   ```

4. **Convert to UUID in task**:
   ```python
   # restore_tenant_context handles conversion
   restore_tenant_context(tenant_id)  # Accept string or UUID
   ```

5. **Log tenant context for debugging**:
   ```python
   @shared_task
   def my_task(*, tenant_id=None):
       restore_tenant_context(tenant_id)
       logger.info(f"Executing task for tenant: {tenant_id}")
       ...
   ```

6. **Create wrapper tasks for scheduled execution with rate limiting**:
   ```python
   # ✅ Good - rate-limited per-tenant tasks (recommended)
   @shared_task
   def scheduled_my_task_all_tenants():
       from documents.tasks import spawn_tenant_tasks_with_rate_limiting
       from paperless.models import Tenant

       tenants = Tenant.objects.filter(is_active=True)
       spawn_tenant_tasks_with_rate_limiting(
           tenants=tenants,
           task_callable=my_task.delay,
           task_name="my_task",
       )

   # ⚠️ Acceptable - manual loop (not recommended for many tenants)
   @shared_task
   def scheduled_my_task_all_tenants():
       for tenant in Tenant.objects.filter(is_active=True):
           my_task.delay(tenant_id=str(tenant.id))

   # ❌ Bad - single scheduled task without wrapper
   # Would need manual tenant_id specification
   ```

7. **Configure rate limiting for your deployment**:
   ```bash
   # For small deployments (<10 tenants)
   CELERY_TENANT_BATCH_SIZE=0
   CELERY_TENANT_BATCH_DELAY=0

   # For medium deployments (10-100 tenants)
   CELERY_TENANT_BATCH_SIZE=10
   CELERY_TENANT_BATCH_DELAY=60

   # For large deployments (100+ tenants)
   CELERY_TENANT_BATCH_SIZE=20
   CELERY_TENANT_BATCH_DELAY=120
   ```

8. **Write tests for tenant isolation**:
   ```python
   def test_my_task_isolates_tenant_data(self):
       tenant1 = create_tenant()
       tenant2 = create_tenant()

       # Task with tenant1
       my_task(tenant_id=str(tenant1.id))

       # Verify only tenant1 data was modified
       assert Document.objects.filter(tenant_id=tenant1.id).count() > 0
       assert Document.objects.filter(tenant_id=tenant2.id).count() == 0
   ```

## References

- [Celery Documentation](https://docs.celeryproject.org/)
- [Django PostgreSQL Row-Level Security](https://docs.djangoproject.com/en/stable/ref/databases/#postgresql-notes)
- [Redis Configuration Guide](./redis-celery-configuration.md)
- [Multi-Tenant Architecture](./multi-tenant-architecture.md)
