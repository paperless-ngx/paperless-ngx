"""
AI Webhooks Module for IntelliDocs-ngx

This module provides a webhook system for notifying external systems about AI events.
It includes:
- Webhook configuration models
- Event tracking and logging
- Retry logic with exponential backoff
- Support for multiple webhook events

According to issue requirements:
- Webhook when AI creates deletion request
- Webhook when AI applies suggestion automatically
- Webhook when AI scan completes
- Configurable via settings
- Robust retry logic with exponential backoff
- Comprehensive logging
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from documents.models import Document, DeletionRequest

logger = logging.getLogger("paperless.ai_webhooks")


class AIWebhookEvent(models.Model):
    """
    Model to track AI webhook events and their delivery status.
    
    Provides comprehensive logging of all webhook attempts for auditing
    and troubleshooting purposes.
    """
    
    # Event types
    EVENT_DELETION_REQUEST_CREATED = 'deletion_request_created'
    EVENT_SUGGESTION_AUTO_APPLIED = 'suggestion_auto_applied'
    EVENT_SCAN_COMPLETED = 'scan_completed'
    
    EVENT_TYPE_CHOICES = [
        (EVENT_DELETION_REQUEST_CREATED, _('Deletion Request Created')),
        (EVENT_SUGGESTION_AUTO_APPLIED, _('Suggestion Auto Applied')),
        (EVENT_SCAN_COMPLETED, _('AI Scan Completed')),
    ]
    
    # Event metadata
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPE_CHOICES,
        help_text=_("Type of AI event that triggered this webhook"),
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Configuration used
    webhook_url = models.CharField(
        max_length=512,
        help_text=_("URL where the webhook was sent"),
    )
    
    # Payload information
    payload = models.JSONField(
        help_text=_("Data sent in the webhook"),
    )
    
    # Delivery tracking
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_RETRYING = 'retrying'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_SUCCESS, _('Success')),
        (STATUS_FAILED, _('Failed')),
        (STATUS_RETRYING, _('Retrying')),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    
    attempts = models.PositiveIntegerField(
        default=0,
        help_text=_("Number of delivery attempts"),
    )
    
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    
    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    
    error_message = models.TextField(
        blank=True,
        help_text=_("Error message if delivery failed"),
    )
    
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("AI webhook event")
        verbose_name_plural = _("AI webhook events")
        indexes = [
            models.Index(fields=['event_type', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"AI Webhook {self.event_type} - {self.status} ({self.attempts} attempts)"


class AIWebhookConfig(models.Model):
    """
    Configuration model for AI webhooks.
    
    Allows multiple webhook endpoints with different configurations
    per event type.
    """
    
    name = models.CharField(
        max_length=128,
        unique=True,
        help_text=_("Friendly name for this webhook configuration"),
    )
    
    enabled = models.BooleanField(
        default=True,
        help_text=_("Whether this webhook is active"),
    )
    
    # Webhook destination
    url = models.CharField(
        max_length=512,
        help_text=_("URL to send webhook notifications"),
    )
    
    # Event filters
    events = models.JSONField(
        default=list,
        help_text=_("List of event types this webhook should receive"),
    )
    
    # Request configuration
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Custom HTTP headers to include in webhook requests"),
    )
    
    secret = models.CharField(
        max_length=256,
        blank=True,
        help_text=_("Secret key for signing webhook payloads (optional)"),
    )
    
    # Retry configuration
    max_retries = models.PositiveIntegerField(
        default=3,
        help_text=_("Maximum number of retry attempts"),
    )
    
    retry_delay = models.PositiveIntegerField(
        default=60,
        help_text=_("Initial retry delay in seconds (will increase exponentially)"),
    )
    
    timeout = models.PositiveIntegerField(
        default=10,
        help_text=_("Request timeout in seconds"),
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_webhook_configs',
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = _("AI webhook configuration")
        verbose_name_plural = _("AI webhook configurations")
    
    def __str__(self):
        return f"{self.name} ({'enabled' if self.enabled else 'disabled'})"
    
    def should_send_event(self, event_type: str) -> bool:
        """Check if this webhook should receive the given event type."""
        return self.enabled and (not self.events or event_type in self.events)


def _validate_webhook_url(url: str) -> bool:
    """
    Validate webhook URL for security.
    
    Uses similar validation as existing webhook system in handlers.py
    """
    try:
        p = urlparse(url)
        
        # Check scheme
        allowed_schemes = getattr(settings, 'WEBHOOKS_ALLOWED_SCHEMES', ['http', 'https'])
        if p.scheme.lower() not in allowed_schemes or not p.hostname:
            logger.warning(f"AI Webhook blocked: invalid scheme/hostname for {url}")
            return False
        
        # Check port if configured
        port = p.port or (443 if p.scheme == "https" else 80)
        allowed_ports = getattr(settings, 'WEBHOOKS_ALLOWED_PORTS', [])
        if allowed_ports and port not in allowed_ports:
            logger.warning(f"AI Webhook blocked: port {port} not permitted for {url}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating webhook URL {url}: {e}")
        return False


def _sign_payload(payload: Dict[str, Any], secret: str) -> str:
    """
    Create HMAC signature for webhook payload.
    
    This allows receivers to verify the webhook came from our system.
    """
    import hmac
    import json
    
    payload_str = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"sha256={signature}"


@shared_task(
    bind=True,
    max_retries=None,  # We handle retries manually
    autoretry_for=None,
)
def send_ai_webhook_task(
    self,
    webhook_event_id: int,
    attempt: int = 1,
):
    """
    Celery task to send AI webhook with retry logic.
    
    Implements exponential backoff for retries.
    """
    try:
        event = AIWebhookEvent.objects.get(pk=webhook_event_id)
    except AIWebhookEvent.DoesNotExist:
        logger.error(f"AI Webhook event {webhook_event_id} not found")
        return
    
    # Get configuration
    try:
        config = AIWebhookConfig.objects.get(url=event.webhook_url, enabled=True)
    except AIWebhookConfig.DoesNotExist:
        # Use default settings if no config exists
        max_retries = getattr(settings, 'PAPERLESS_AI_WEBHOOKS_MAX_RETRIES', 3)
        retry_delay = getattr(settings, 'PAPERLESS_AI_WEBHOOKS_RETRY_DELAY', 60)
        timeout = getattr(settings, 'PAPERLESS_AI_WEBHOOKS_TIMEOUT', 10)
        headers = {}
        secret = None
    else:
        max_retries = config.max_retries
        retry_delay = config.retry_delay
        timeout = config.timeout
        headers = config.headers or {}
        secret = config.secret
    
    # Update attempt tracking
    event.attempts = attempt
    event.last_attempt_at = timezone.now()
    event.status = AIWebhookEvent.STATUS_RETRYING if attempt > 1 else AIWebhookEvent.STATUS_PENDING
    event.save()
    
    # Prepare headers
    request_headers = headers.copy()
    request_headers['Content-Type'] = 'application/json'
    request_headers['User-Agent'] = 'IntelliDocs-AI-Webhook/1.0'
    
    # Add signature if secret is configured
    if secret:
        signature = _sign_payload(event.payload, secret)
        request_headers['X-IntelliDocs-Signature'] = signature
    
    try:
        # Send webhook
        response = httpx.post(
            event.webhook_url,
            json=event.payload,
            headers=request_headers,
            timeout=timeout,
            follow_redirects=False,
        )
        
        # Update event with response
        event.response_status_code = response.status_code
        event.response_body = response.text[:1000]  # Limit stored response size
        
        # Check if successful (2xx status code)
        if 200 <= response.status_code < 300:
            event.status = AIWebhookEvent.STATUS_SUCCESS
            event.completed_at = timezone.now()
            event.save()
            
            logger.info(
                f"AI Webhook sent successfully to {event.webhook_url} "
                f"for {event.event_type} (attempt {attempt})"
            )
            return
        
        # Non-2xx response
        error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
        event.error_message = error_msg
        
        # Retry if we haven't exceeded max attempts
        if attempt < max_retries:
            event.save()
            
            # Calculate exponential backoff delay
            delay = retry_delay * (2 ** (attempt - 1))
            
            logger.warning(
                f"AI Webhook to {event.webhook_url} failed with status {response.status_code}, "
                f"retrying in {delay}s (attempt {attempt}/{max_retries})"
            )
            
            # Schedule retry
            send_ai_webhook_task.apply_async(
                args=[webhook_event_id, attempt + 1],
                countdown=delay,
            )
        else:
            event.status = AIWebhookEvent.STATUS_FAILED
            event.completed_at = timezone.now()
            event.save()
            
            logger.error(
                f"AI Webhook to {event.webhook_url} failed after {max_retries} attempts: {error_msg}"
            )
    
    except Exception as e:
        error_msg = str(e)
        event.error_message = error_msg
        
        # Retry if we haven't exceeded max attempts
        if attempt < max_retries:
            event.save()
            
            # Calculate exponential backoff delay
            delay = retry_delay * (2 ** (attempt - 1))
            
            logger.warning(
                f"AI Webhook to {event.webhook_url} failed with error: {error_msg}, "
                f"retrying in {delay}s (attempt {attempt}/{max_retries})"
            )
            
            # Schedule retry
            send_ai_webhook_task.apply_async(
                args=[webhook_event_id, attempt + 1],
                countdown=delay,
            )
        else:
            event.status = AIWebhookEvent.STATUS_FAILED
            event.completed_at = timezone.now()
            event.save()
            
            logger.error(
                f"AI Webhook to {event.webhook_url} failed after {max_retries} attempts: {error_msg}"
            )


def send_ai_webhook(
    event_type: str,
    payload: Dict[str, Any],
    webhook_urls: Optional[list] = None,
) -> list:
    """
    Send AI webhook notification.
    
    Args:
        event_type: Type of event (e.g., 'deletion_request_created')
        payload: Data to send in webhook
        webhook_urls: Optional list of URLs to send to (uses config if not provided)
        
    Returns:
        List of created AIWebhookEvent instances
    """
    # Check if webhooks are enabled
    if not getattr(settings, 'PAPERLESS_AI_WEBHOOKS_ENABLED', False):
        logger.debug("AI webhooks are disabled in settings")
        return []
    
    # Add metadata to payload
    payload['event_type'] = event_type
    payload['timestamp'] = timezone.now().isoformat()
    payload['source'] = 'intellidocs-ai'
    
    events = []
    
    # Get webhook URLs from config or parameter
    if webhook_urls:
        urls = webhook_urls
    else:
        # Get all enabled configs for this event type
        configs = AIWebhookConfig.objects.filter(enabled=True)
        urls = [
            config.url
            for config in configs
            if config.should_send_event(event_type)
        ]
    
    if not urls:
        logger.debug(f"No webhook URLs configured for event type: {event_type}")
        return []
    
    # Create webhook events and queue tasks
    for url in urls:
        # Validate URL
        if not _validate_webhook_url(url):
            logger.warning(f"Skipping invalid webhook URL: {url}")
            continue
        
        # Create event record
        event = AIWebhookEvent.objects.create(
            event_type=event_type,
            webhook_url=url,
            payload=payload,
            status=AIWebhookEvent.STATUS_PENDING,
        )
        
        events.append(event)
        
        # Queue async task
        send_ai_webhook_task.delay(event.id)
        
        logger.debug(f"Queued AI webhook {event_type} to {url}")
    
    return events


# Helper functions for specific webhook events

def send_deletion_request_webhook(deletion_request: DeletionRequest) -> list:
    """
    Send webhook when AI creates a deletion request.
    
    Args:
        deletion_request: The DeletionRequest instance
        
    Returns:
        List of created webhook events
    """
    from documents.models import Document
    
    # Build payload
    documents_data = []
    for doc in deletion_request.documents.all():
        documents_data.append({
            'id': doc.id,
            'title': doc.title,
            'created': doc.created.isoformat() if doc.created else None,
            'correspondent': doc.correspondent.name if doc.correspondent else None,
            'document_type': doc.document_type.name if doc.document_type else None,
        })
    
    payload = {
        'deletion_request': {
            'id': deletion_request.id,
            'status': deletion_request.status,
            'ai_reason': deletion_request.ai_reason,
            'document_count': deletion_request.documents.count(),
            'documents': documents_data,
            'impact_summary': deletion_request.impact_summary,
            'created_at': deletion_request.created_at.isoformat(),
        },
        'user': {
            'id': deletion_request.user.id,
            'username': deletion_request.user.username,
        }
    }
    
    return send_ai_webhook(
        AIWebhookEvent.EVENT_DELETION_REQUEST_CREATED,
        payload,
    )


def send_suggestion_applied_webhook(
    document: Document,
    suggestions: Dict[str, Any],
    applied_fields: list,
) -> list:
    """
    Send webhook when AI automatically applies suggestions.
    
    Args:
        document: The Document that was updated
        suggestions: Dictionary of all AI suggestions
        applied_fields: List of fields that were auto-applied
        
    Returns:
        List of created webhook events
    """
    payload = {
        'document': {
            'id': document.id,
            'title': document.title,
            'created': document.created.isoformat() if document.created else None,
            'correspondent': document.correspondent.name if document.correspondent else None,
            'document_type': document.document_type.name if document.document_type else None,
            'tags': [tag.name for tag in document.tags.all()],
        },
        'applied_suggestions': {
            field: suggestions.get(field)
            for field in applied_fields
        },
        'auto_applied': True,
    }
    
    return send_ai_webhook(
        AIWebhookEvent.EVENT_SUGGESTION_AUTO_APPLIED,
        payload,
    )


def send_scan_completed_webhook(
    document: Document,
    scan_results: Dict[str, Any],
    auto_applied_count: int = 0,
    suggestions_count: int = 0,
) -> list:
    """
    Send webhook when AI scan completes.
    
    Args:
        document: The Document that was scanned
        scan_results: Dictionary of scan results
        auto_applied_count: Number of suggestions that were auto-applied
        suggestions_count: Number of suggestions pending review
        
    Returns:
        List of created webhook events
    """
    payload = {
        'document': {
            'id': document.id,
            'title': document.title,
            'created': document.created.isoformat() if document.created else None,
            'correspondent': document.correspondent.name if document.correspondent else None,
            'document_type': document.document_type.name if document.document_type else None,
        },
        'scan_summary': {
            'auto_applied_count': auto_applied_count,
            'suggestions_count': suggestions_count,
            'has_tags_suggestions': 'tags' in scan_results,
            'has_correspondent_suggestion': 'correspondent' in scan_results,
            'has_type_suggestion': 'document_type' in scan_results,
            'has_storage_path_suggestion': 'storage_path' in scan_results,
            'has_custom_fields': 'custom_fields' in scan_results and scan_results['custom_fields'],
            'has_workflow_suggestions': 'workflows' in scan_results and scan_results['workflows'],
        },
        'scan_completed_at': timezone.now().isoformat(),
    }
    
    return send_ai_webhook(
        AIWebhookEvent.EVENT_SCAN_COMPLETED,
        payload,
    )
