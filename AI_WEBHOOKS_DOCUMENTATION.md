# AI Webhooks System - IntelliDocs

## Overview

The AI Webhooks system provides real-time notifications for AI events in IntelliDocs. This allows external systems to be notified when the AI performs important actions, enabling integration with workflow automation tools, monitoring systems, and custom applications.

## Features

- **Event Tracking**: Comprehensive logging of all webhook events
- **Retry Logic**: Exponential backoff for failed webhook deliveries
- **Configurable**: Multiple webhook endpoints with different configurations
- **Secure**: Optional HMAC signature validation
- **Robust**: Graceful degradation if webhook delivery fails

## Supported Events

### 1. Deletion Request Created (`deletion_request_created`)

Triggered when the AI creates a deletion request that requires user approval.

**Payload Example:**
```json
{
  "event_type": "deletion_request_created",
  "timestamp": "2025-11-14T15:00:00Z",
  "source": "intellidocs-ai",
  "deletion_request": {
    "id": 123,
    "status": "pending",
    "ai_reason": "Duplicate document detected...",
    "document_count": 3,
    "documents": [
      {
        "id": 456,
        "title": "Invoice 2023-001",
        "created": "2023-01-15T10:30:00Z",
        "correspondent": "Acme Corp",
        "document_type": "Invoice"
      }
    ],
    "impact_summary": {
      "document_count": 3,
      "affected_tags": ["invoices", "2023"],
      "affected_correspondents": ["Acme Corp"],
      "date_range": {
        "earliest": "2023-01-15",
        "latest": "2023-03-20"
      }
    },
    "created_at": "2025-11-14T15:00:00Z"
  },
  "user": {
    "id": 1,
    "username": "admin"
  }
}
```

### 2. Suggestion Auto Applied (`suggestion_auto_applied`)

Triggered when the AI automatically applies suggestions with high confidence (≥80%).

**Payload Example:**
```json
{
  "event_type": "suggestion_auto_applied",
  "timestamp": "2025-11-14T15:00:00Z",
  "source": "intellidocs-ai",
  "document": {
    "id": 789,
    "title": "Contract 2025-A",
    "created": "2025-11-14T14:30:00Z",
    "correspondent": "TechCorp",
    "document_type": "Contract",
    "tags": ["contracts", "2025", "legal"]
  },
  "applied_suggestions": {
    "tags": [
      {"id": 10, "name": "contracts"},
      {"id": 25, "name": "legal"}
    ],
    "correspondent": {
      "id": 5,
      "name": "TechCorp"
    },
    "document_type": {
      "id": 3,
      "name": "Contract"
    }
  },
  "auto_applied": true
}
```

### 3. AI Scan Completed (`scan_completed`)

Triggered when an AI scan of a document is completed.

**Payload Example:**
```json
{
  "event_type": "scan_completed",
  "timestamp": "2025-11-14T15:00:00Z",
  "source": "intellidocs-ai",
  "document": {
    "id": 999,
    "title": "Report Q4 2025",
    "created": "2025-11-14T14:45:00Z",
    "correspondent": "Finance Dept",
    "document_type": "Report"
  },
  "scan_summary": {
    "auto_applied_count": 3,
    "suggestions_count": 2,
    "has_tags_suggestions": true,
    "has_correspondent_suggestion": true,
    "has_type_suggestion": true,
    "has_storage_path_suggestion": false,
    "has_custom_fields": true,
    "has_workflow_suggestions": false
  },
  "scan_completed_at": "2025-11-14T15:00:00Z"
}
```

## Configuration

### Environment Variables

Add these settings to your environment or `paperless.conf`:

```bash
# Enable AI webhooks (disabled by default)
PAPERLESS_AI_WEBHOOKS_ENABLED=true

# Maximum retry attempts for failed webhooks (default: 3)
PAPERLESS_AI_WEBHOOKS_MAX_RETRIES=3

# Initial retry delay in seconds (default: 60)
# Increases exponentially: 60s, 120s, 240s...
PAPERLESS_AI_WEBHOOKS_RETRY_DELAY=60

# Request timeout in seconds (default: 10)
PAPERLESS_AI_WEBHOOKS_TIMEOUT=10
```

### Django Admin Configuration

1. Navigate to **Admin** → **AI webhook configurations**
2. Click **Add AI webhook configuration**
3. Fill in the form:
   - **Name**: Friendly name (e.g., "Slack Notifications")
   - **Enabled**: Check to activate
   - **URL**: Webhook endpoint URL
   - **Events**: List of event types (leave empty for all events)
   - **Headers**: Optional custom headers (JSON format)
   - **Secret**: Optional secret key for HMAC signing
   - **Max retries**: Number of retry attempts (default: 3)
   - **Retry delay**: Initial delay in seconds (default: 60)
   - **Timeout**: Request timeout in seconds (default: 10)

**Example Configuration:**

```json
{
  "name": "Slack AI Notifications",
  "enabled": true,
  "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
  "events": ["deletion_request_created", "suggestion_auto_applied"],
  "headers": {
    "Content-Type": "application/json"
  },
  "secret": "your-secret-key-here",
  "max_retries": 3,
  "retry_delay": 60,
  "timeout": 10
}
```

## Security

### URL Validation

Webhooks use the same security validation as the existing workflow webhook system:

- Only allowed URL schemes (http, https by default)
- Port restrictions if configured
- Optional internal request blocking

### HMAC Signature Verification

If a secret is configured, webhooks include an HMAC signature in the `X-IntelliDocs-Signature` header.

**Verification Example (Python):**

```python
import hmac
import hashlib
import json

def verify_webhook(payload, signature, secret):
    """Verify webhook HMAC signature"""
    payload_str = json.dumps(payload, sort_keys=True)
    expected = hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Signature format: "sha256={hash}"
    expected_sig = f"sha256={expected}"
    return hmac.compare_digest(expected_sig, signature)

# Usage
secret = "your-secret-key"
signature = request.headers.get('X-IntelliDocs-Signature')
payload = request.json

if verify_webhook(payload, signature, secret):
    print("Webhook verified!")
else:
    print("Invalid signature!")
```

## Retry Logic

Failed webhooks are automatically retried with exponential backoff:

1. **Attempt 1**: Immediate
2. **Attempt 2**: After `retry_delay` seconds (default: 60s)
3. **Attempt 3**: After `retry_delay * 2` seconds (default: 120s)
4. **Attempt 4**: After `retry_delay * 4` seconds (default: 240s)

After max retries, the webhook is marked as failed and logged.

## Monitoring

### Admin Interface

View webhook delivery status in **Admin** → **AI webhook events**:

- **Event Type**: Type of AI event
- **Status**: pending, success, failed, retrying
- **Attempts**: Number of delivery attempts
- **Response**: HTTP status code and response body
- **Error Message**: Details if delivery failed

### Logging

All webhook activity is logged to `paperless.ai_webhooks`:

```python
import logging
logger = logging.getLogger("paperless.ai_webhooks")
```

**Log Levels:**
- `INFO`: Successful deliveries
- `WARNING`: Failed deliveries being retried
- `ERROR`: Permanent failures after max retries
- `DEBUG`: Detailed webhook activity

## Integration Examples

### Slack

Create a Slack app with incoming webhooks and use the webhook URL:

```json
{
  "name": "Slack Notifications",
  "url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX",
  "events": ["deletion_request_created"]
}
```

### Discord

Use Discord's webhook feature:

```json
{
  "name": "Discord Notifications",
  "url": "https://discord.com/api/webhooks/123456789/abcdefg",
  "events": ["suggestion_auto_applied", "scan_completed"]
}
```

### Custom HTTP Endpoint

Create your own webhook receiver:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    event = request.json
    event_type = event.get('event_type')
    
    if event_type == 'deletion_request_created':
        # Handle deletion request
        deletion_request = event['deletion_request']
        print(f"Deletion request {deletion_request['id']} created")
    
    elif event_type == 'suggestion_auto_applied':
        # Handle auto-applied suggestion
        document = event['document']
        print(f"Suggestions applied to document {document['id']}")
    
    elif event_type == 'scan_completed':
        # Handle scan completion
        scan_summary = event['scan_summary']
        print(f"Scan completed: {scan_summary}")
    
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(port=5000)
```

## Troubleshooting

### Webhooks Not Being Sent

1. Check `PAPERLESS_AI_WEBHOOKS_ENABLED=true` in settings
2. Verify webhook configuration is enabled in admin
3. Check that events list includes the event type (or is empty for all events)
4. Review logs for errors: `grep "ai_webhooks" /path/to/paperless.log`

### Failed Deliveries

1. Check webhook event status in admin
2. Review error message and response code
3. Verify endpoint URL is accessible
4. Check firewall/network settings
5. Verify HMAC signature if using secrets

### High Retry Count

1. Increase `PAPERLESS_AI_WEBHOOKS_TIMEOUT` if endpoint is slow
2. Increase `PAPERLESS_AI_WEBHOOKS_MAX_RETRIES` for unreliable networks
3. Check endpoint logs for errors
4. Consider using a message queue for reliability

## Database Models

### AIWebhookEvent

Tracks individual webhook delivery attempts.

**Fields:**
- `event_type`: Type of event
- `webhook_url`: Destination URL
- `payload`: Event data (JSON)
- `status`: pending/success/failed/retrying
- `attempts`: Number of delivery attempts
- `response_status_code`: HTTP response code
- `error_message`: Error details if failed

### AIWebhookConfig

Stores webhook endpoint configurations.

**Fields:**
- `name`: Configuration name
- `enabled`: Active status
- `url`: Webhook URL
- `events`: Filtered event types (empty = all)
- `headers`: Custom HTTP headers
- `secret`: HMAC signing key
- `max_retries`: Retry limit
- `retry_delay`: Initial retry delay
- `timeout`: Request timeout

## Performance Considerations

- Webhook delivery is **asynchronous** via Celery tasks
- Failed webhooks don't block document processing
- Event records are kept for auditing (consider periodic cleanup)
- Network failures are handled gracefully

## Best Practices

1. **Use HTTPS**: Always use HTTPS webhooks in production
2. **Validate Signatures**: Use HMAC signatures to verify authenticity
3. **Filter Events**: Only subscribe to needed events
4. **Monitor Failures**: Regularly check failed webhooks in admin
5. **Set Appropriate Timeouts**: Balance reliability vs. performance
6. **Test Endpoints**: Verify webhook receivers work before enabling
7. **Log Everything**: Keep comprehensive logs for debugging

## Migration

The webhook system requires database migration:

```bash
python manage.py migrate documents
```

This creates the `AIWebhookEvent` and `AIWebhookConfig` tables.

## API Reference

### Python API

```python
from documents.webhooks import (
    send_ai_webhook,
    send_deletion_request_webhook,
    send_suggestion_applied_webhook,
    send_scan_completed_webhook,
)

# Send generic webhook
send_ai_webhook('custom_event', {'data': 'value'})

# Send specific event webhooks (called automatically by AI scanner)
send_deletion_request_webhook(deletion_request)
send_suggestion_applied_webhook(document, suggestions, applied_fields)
send_scan_completed_webhook(document, scan_results, auto_count, suggest_count)
```

## Related Documentation

- [AI Scanner Implementation](./AI_SCANNER_IMPLEMENTATION.md)
- [AI Scanner Improvement Plan](./AI_SCANNER_IMPROVEMENT_PLAN.md)
- [API REST Endpoints](./GITHUB_ISSUES_TEMPLATE.md)

## Support

For issues or questions:
- GitHub Issues: [dawnsystem/IntelliDocs-ngx](https://github.com/dawnsystem/IntelliDocs-ngx/issues)
- Check logs: `paperless.ai_webhooks` logger
- Review admin interface for webhook event details

---

**Version**: 1.0  
**Last Updated**: 2025-11-14  
**Status**: Production Ready
