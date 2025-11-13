# Generated manually for DeletionRequest performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add performance indexes for DeletionRequest model.
    
    These indexes optimize common query patterns:
    - Filtering by user + status + created_at (most common listing query)
    - Filtering by reviewed_at (for finding reviewed requests)
    - Filtering by completed_at (for finding completed requests)
    
    Expected performance improvement:
    - List queries: <100ms
    - Filter queries: <50ms
    
    Addresses Issue: [AI Scanner] Índices de Performance para DeletionRequest
    Epic: Migraciones de Base de Datos
    """

    dependencies = [
        ("documents", "1075_add_performance_indexes"),
    ]

    operations = [
        # Composite index for user + status + created_at (most common query pattern)
        # This supports queries like: DeletionRequest.objects.filter(user=user, status='pending').order_by('-created_at')
        migrations.AddIndex(
            model_name="deletionrequest",
            index=models.Index(
                fields=["user", "status", "created_at"],
                name="delreq_user_status_created_idx",
            ),
        ),
        # Index for reviewed_at (for filtering reviewed requests)
        # Supports queries like: DeletionRequest.objects.filter(reviewed_at__isnull=False)
        migrations.AddIndex(
            model_name="deletionrequest",
            index=models.Index(
                fields=["reviewed_at"],
                name="delreq_reviewed_at_idx",
            ),
        ),
        # Index for completed_at (for filtering completed requests)
        # Supports queries like: DeletionRequest.objects.filter(completed_at__isnull=False)
        migrations.AddIndex(
            model_name="deletionrequest",
            index=models.Index(
                fields=["completed_at"],
                name="delreq_completed_at_idx",
            ),
        ),
    ]
