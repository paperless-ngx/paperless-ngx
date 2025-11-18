# AI Suggestions API Documentation

This document describes the AI Suggestions API endpoints for the IntelliDocs-ngx project.

## Overview

The AI Suggestions API allows frontend applications to:

1. Retrieve AI-generated suggestions for document metadata
2. Apply suggestions to documents
3. Reject suggestions (for user feedback)
4. View accuracy statistics for AI model improvement

## Authentication

All endpoints require authentication. Include the authentication token in the request headers:

```http
Authorization: Token <your-auth-token>
```

## Endpoints

### 1. Get AI Suggestions

Retrieve AI-generated suggestions for a specific document.

**Endpoint:** `GET /api/documents/{id}/ai-suggestions/`

**Parameters:**

-   `id` (path parameter): Document ID

**Response:**

```json
{
    "tags": [
        {
            "id": 1,
            "name": "Invoice",
            "color": "#FF5733",
            "confidence": 0.85
        },
        {
            "id": 2,
            "name": "Important",
            "color": "#33FF57",
            "confidence": 0.75
        }
    ],
    "correspondent": {
        "id": 5,
        "name": "Acme Corporation",
        "confidence": 0.9
    },
    "document_type": {
        "id": 3,
        "name": "Invoice",
        "confidence": 0.88
    },
    "storage_path": {
        "id": 2,
        "name": "Financial Documents",
        "path": "/documents/financial/",
        "confidence": 0.8
    },
    "custom_fields": [
        {
            "field_id": 1,
            "field_name": "Invoice Number",
            "value": "INV-2024-001",
            "confidence": 0.92
        }
    ],
    "workflows": [
        {
            "id": 4,
            "name": "Invoice Processing",
            "confidence": 0.78
        }
    ],
    "title_suggestion": {
        "title": "Invoice - Acme Corporation - 2024-01-15"
    }
}
```

**Error Responses:**

-   `400 Bad Request`: Document has no content to analyze
-   `404 Not Found`: Document not found
-   `500 Internal Server Error`: Error generating suggestions

---

### 2. Apply Suggestion

Apply an AI suggestion to a document and record user feedback.

**Endpoint:** `POST /api/documents/{id}/apply-suggestion/`

**Parameters:**

-   `id` (path parameter): Document ID

**Request Body:**

```json
{
    "suggestion_type": "tag",
    "value_id": 1,
    "confidence": 0.85
}
```

**Supported Suggestion Types:**

-   `tag` - Tag assignment
-   `correspondent` - Correspondent assignment
-   `document_type` - Document type classification
-   `storage_path` - Storage path assignment
-   `title` - Document title

**Note:** Custom field and workflow suggestions are supported in the API response but not yet implemented in the apply endpoint.

**For ID-based suggestions (tag, correspondent, document_type, storage_path):**

```json
{
    "suggestion_type": "correspondent",
    "value_id": 5,
    "confidence": 0.9
}
```

**For text-based suggestions (title):**

```json
{
    "suggestion_type": "title",
    "value_text": "New Document Title",
    "confidence": 0.8
}
```

**Response:**

```json
{
    "status": "success",
    "message": "Tag 'Invoice' applied"
}
```

**Error Responses:**

-   `400 Bad Request`: Invalid suggestion type or missing value
-   `404 Not Found`: Referenced object not found
-   `500 Internal Server Error`: Error applying suggestion

---

### 3. Reject Suggestion

Reject an AI suggestion and record user feedback for model improvement.

**Endpoint:** `POST /api/documents/{id}/reject-suggestion/`

**Parameters:**

-   `id` (path parameter): Document ID

**Request Body:**

```json
{
    "suggestion_type": "tag",
    "value_id": 2,
    "confidence": 0.65
}
```

Same format as apply-suggestion endpoint.

**Response:**

```json
{
    "status": "success",
    "message": "Suggestion rejected and feedback recorded"
}
```

**Error Responses:**

-   `400 Bad Request`: Invalid request data
-   `500 Internal Server Error`: Error recording feedback

---

### 4. AI Suggestion Statistics

Get accuracy statistics and metrics for AI suggestions.

**Endpoint:** `GET /api/documents/ai-suggestion-stats/`

**Response:**

```json
{
    "total_suggestions": 150,
    "total_applied": 120,
    "total_rejected": 30,
    "accuracy_rate": 80.0,
    "by_type": {
        "tag": {
            "total": 50,
            "applied": 45,
            "rejected": 5,
            "accuracy_rate": 90.0
        },
        "correspondent": {
            "total": 40,
            "applied": 35,
            "rejected": 5,
            "accuracy_rate": 87.5
        },
        "document_type": {
            "total": 30,
            "applied": 20,
            "rejected": 10,
            "accuracy_rate": 66.67
        },
        "storage_path": {
            "total": 20,
            "applied": 15,
            "rejected": 5,
            "accuracy_rate": 75.0
        },
        "title": {
            "total": 10,
            "applied": 5,
            "rejected": 5,
            "accuracy_rate": 50.0
        }
    },
    "average_confidence_applied": 0.82,
    "average_confidence_rejected": 0.58,
    "recent_suggestions": [
        {
            "id": 150,
            "document": 42,
            "suggestion_type": "tag",
            "suggested_value_id": 5,
            "suggested_value_text": "",
            "confidence": 0.85,
            "status": "applied",
            "user": 1,
            "created_at": "2024-01-15T10:30:00Z",
            "applied_at": "2024-01-15T10:30:05Z",
            "metadata": {}
        }
    ]
}
```

**Error Responses:**

-   `500 Internal Server Error`: Error calculating statistics

---

## Frontend Integration Example

### React/TypeScript Example

```typescript
import axios from 'axios'

const API_BASE = '/api/documents'

interface AISuggestions {
    tags?: Array<{ id: number; name: string; confidence: number }>
    correspondent?: { id: number; name: string; confidence: number }
    document_type?: { id: number; name: string; confidence: number }
    // ... other fields
}

// Get AI suggestions
async function getAISuggestions(documentId: number): Promise<AISuggestions> {
    const response = await axios.get(
        `${API_BASE}/${documentId}/ai-suggestions/`
    )
    return response.data
}

// Apply a suggestion
async function applySuggestion(
    documentId: number,
    type: string,
    valueId: number,
    confidence: number
): Promise<void> {
    await axios.post(`${API_BASE}/${documentId}/apply-suggestion/`, {
        suggestion_type: type,
        value_id: valueId,
        confidence: confidence,
    })
}

// Reject a suggestion
async function rejectSuggestion(
    documentId: number,
    type: string,
    valueId: number,
    confidence: number
): Promise<void> {
    await axios.post(`${API_BASE}/${documentId}/reject-suggestion/`, {
        suggestion_type: type,
        value_id: valueId,
        confidence: confidence,
    })
}

// Get statistics
async function getStatistics() {
    const response = await axios.get(`${API_BASE}/ai-suggestion-stats/`)
    return response.data
}

// Usage example
async function handleDocument(documentId: number) {
    try {
        // Get suggestions
        const suggestions = await getAISuggestions(documentId)

        // Show suggestions to user
        if (suggestions.tags) {
            suggestions.tags.forEach((tag) => {
                console.log(
                    `Suggested tag: ${tag.name} (${tag.confidence * 100}%)`
                )
            })
        }

        // User accepts a tag suggestion
        if (suggestions.tags && suggestions.tags.length > 0) {
            const tag = suggestions.tags[0]
            await applySuggestion(documentId, 'tag', tag.id, tag.confidence)
            console.log('Tag applied successfully')
        }
    } catch (error) {
        console.error('Error handling AI suggestions:', error)
    }
}
```

---

## Database Schema

### AISuggestionFeedback Model

Stores user feedback on AI suggestions for accuracy tracking and model improvement.

**Fields:**

-   `id` (BigAutoField): Primary key
-   `document` (ForeignKey): Reference to Document
-   `suggestion_type` (CharField): Type of suggestion (tag, correspondent, etc.)
-   `suggested_value_id` (IntegerField, nullable): ID of suggested object
-   `suggested_value_text` (TextField): Text representation of suggestion
-   `confidence` (FloatField): AI confidence score (0.0 to 1.0)
-   `status` (CharField): 'applied' or 'rejected'
-   `user` (ForeignKey, nullable): User who provided feedback
-   `created_at` (DateTimeField): When suggestion was created
-   `applied_at` (DateTimeField): When feedback was recorded
-   `metadata` (JSONField): Additional metadata

**Indexes:**

-   `(document, suggestion_type)`
-   `(status, created_at)`
-   `(suggestion_type, status)`

---

## Best Practices

1. **Confidence Thresholds:**

    - High confidence (≥ 0.80): Can be auto-applied
    - Medium confidence (0.60-0.79): Show to user for review
    - Low confidence (< 0.60): Log but don't suggest

2. **Error Handling:**

    - Always handle 400, 404, and 500 errors gracefully
    - Show user-friendly error messages
    - Log errors for debugging

3. **Performance:**

    - Cache suggestions when possible
    - Use pagination for statistics endpoint if needed
    - Batch apply/reject operations when possible

4. **User Experience:**

    - Show confidence scores to users
    - Allow users to modify suggestions before applying
    - Provide feedback on applied/rejected actions
    - Show statistics to demonstrate AI improvement over time

5. **Privacy:**
    - Only authenticated users can access suggestions
    - Users can only see suggestions for documents they have access to
    - Feedback is tied to user accounts for accountability

---

## Troubleshooting

### No suggestions returned

-   Verify document has content (document.content is not empty)
-   Check if AI scanner is enabled in settings
-   Verify ML models are loaded correctly

### Suggestions not being applied

-   Check user permissions on the document
-   Verify the suggested object (tag, correspondent, etc.) still exists
-   Check application logs for detailed error messages

### Statistics showing 0 accuracy

-   Ensure users are applying or rejecting suggestions
-   Check database for AISuggestionFeedback entries
-   Verify feedback is being recorded with correct status

---

## Future Enhancements

Potential improvements for future versions:

1. Bulk operations (apply/reject multiple suggestions at once)
2. Suggestion confidence threshold configuration per user
3. A/B testing different AI models
4. Machine learning model retraining based on feedback
5. Suggestion explanations (why AI made this suggestion)
6. Custom suggestion rules per user or organization
7. Integration with external AI services
8. Real-time suggestions via WebSocket

---

## Support

For issues or questions:

-   GitHub Issues: https://github.com/dawnsystem/IntelliDocs-ngx/issues
-   Documentation: https://docs.paperless-ngx.com
-   Community: Matrix chat or forum

---

_Last updated: 2024-11-13_
_API Version: 1.0_
