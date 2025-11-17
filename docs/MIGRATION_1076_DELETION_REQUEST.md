# Migration 1076: DeletionRequest Model

## Overview
This migration adds the `DeletionRequest` model to track AI-initiated deletion requests that require explicit user approval.

## Migration Details
- **File**: `src/documents/migrations/1076_add_deletion_request.py`
- **Dependencies**: Migration 1075 (add_performance_indexes)
- **Generated**: Manually based on model definition
- **Django Version**: 5.2+

## What This Migration Does

### Creates DeletionRequest Table
The migration creates a new table `documents_deletionrequest` with the following fields:

#### Core Fields
- `id`: BigAutoField (Primary Key)
- `created_at`: DateTimeField (auto_now_add=True)
- `updated_at`: DateTimeField (auto_now=True)

#### Request Information
- `requested_by_ai`: BooleanField (default=True)
- `ai_reason`: TextField - Detailed explanation from AI
- `status`: CharField(max_length=20) with choices:
  - `pending` (default)
  - `approved`
  - `rejected`
  - `cancelled`
  - `completed`

#### Relationships
- `user`: ForeignKey to User (CASCADE) - User who must approve
- `reviewed_by`: ForeignKey to User (SET_NULL, nullable) - User who reviewed
- `documents`: ManyToManyField to Document - Documents to be deleted

#### Metadata
- `impact_summary`: JSONField - Summary of deletion impact
- `reviewed_at`: DateTimeField (nullable) - When reviewed
- `review_comment`: TextField (blank) - User's review comment
- `completed_at`: DateTimeField (nullable) - When completed
- `completion_details`: JSONField - Execution details

### Custom Indexes
The migration creates two indexes for optimal query performance:

1. **Composite Index**: `del_req_status_user_idx`
   - Fields: `[status, user]`
   - Purpose: Optimize queries filtering by status and user (e.g., "show me all pending requests for this user")

2. **Single Index**: `del_req_created_idx`
   - Fields: `[created_at]`
   - Purpose: Optimize chronological queries and ordering

## How to Apply This Migration

### Development Environment

```bash
cd src
python manage.py migrate documents 1076
```

### Production Environment

1. **Backup your database first**:
   ```bash
   pg_dump paperless > backup_before_1076.sql
   ```

2. **Apply the migration**:
   ```bash
   python manage.py migrate documents 1076
   ```

3. **Verify the migration**:
   ```bash
   python manage.py showmigrations documents
   ```

## Rollback Instructions

If you need to rollback this migration:

```bash
python manage.py migrate documents 1075
```

This will:
- Drop the `documents_deletionrequest` table
- Drop the ManyToMany through table
- Remove the custom indexes

## Backward Compatibility

✅ **This migration is backward compatible**:
- It only adds new tables and indexes
- It does not modify existing tables
- No data migration is required
- Old code will continue to work (new model is optional)

## Data Migration

No data migration is required as this is a new model with no pre-existing data.

## Testing

### Verify Table Creation
```sql
-- Check table exists
SELECT table_name
FROM information_schema.tables
WHERE table_name = 'documents_deletionrequest';

-- Check columns
\d documents_deletionrequest
```

### Verify Indexes
```sql
-- Check indexes exist
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'documents_deletionrequest';
```

### Test Model Operations
```python
from documents.models import DeletionRequest
from django.contrib.auth.models import User

# Create a test deletion request
user = User.objects.first()
dr = DeletionRequest.objects.create(
    user=user,
    ai_reason="Test deletion request",
    status=DeletionRequest.STATUS_PENDING
)

# Verify it was created
assert DeletionRequest.objects.filter(id=dr.id).exists()

# Clean up
dr.delete()
```

## Performance Impact

- **Write Performance**: Minimal impact. Additional table with moderate write frequency expected.
- **Read Performance**: Improved by custom indexes for common query patterns.
- **Storage**: Approximately 1-2 KB per deletion request record.

## Security Considerations

- The migration implements proper foreign key constraints to ensure referential integrity
- CASCADE delete on `user` field ensures cleanup when users are deleted
- SET_NULL on `reviewed_by` preserves audit trail even if reviewer is deleted

## Related Documentation

- Model definition: `src/documents/models.py` (line 1586)
- AI Scanner documentation: `AI_SCANNER_IMPLEMENTATION.md`
- agents.md: Safety requirements section

## Support

If you encounter issues with this migration:
1. Check Django version is 5.2+
2. Verify database supports JSONField (PostgreSQL 9.4+)
3. Check migration dependencies are satisfied
4. Review Django logs for detailed error messages
