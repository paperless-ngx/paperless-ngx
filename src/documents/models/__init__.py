"""
Documents models module.
All models are imported here for easy access.
"""

# Import Django models that are used throughout the app
from django.contrib.auth.models import Group, User

# Import base models and managers
from documents.models.base import (
    ModelWithOwner,
    TenantManager,
    get_current_tenant_id,
    set_current_tenant_id,
)

# Import all models from the main models.py file
from documents.models_legacy import (
    Correspondent,
    CustomField,
    CustomFieldInstance,
    Document,
    DocumentType,
    MatchingModel,
    Note,
    PaperlessTask,
    SavedView,
    SavedViewFilterRule,
    ShareLink,
    StoragePath,
    Tag,
    UiSettings,
    Workflow,
    WorkflowAction,
    WorkflowActionEmail,
    WorkflowActionWebhook,
    WorkflowRun,
    WorkflowTrigger,
)

# Import the new Tenant model
from documents.models.tenant import Tenant

__all__ = [
    # Django auth models
    'User',
    'Group',

    # Core models
    'Tenant',
    'Document',
    'Correspondent',
    'Tag',
    'DocumentType',
    'StoragePath',
    'Note',
    'ShareLink',

    # Base models and managers
    'ModelWithOwner',
    'MatchingModel',
    'TenantManager',

    # Custom fields
    'CustomField',
    'CustomFieldInstance',

    # Saved views
    'SavedView',
    'SavedViewFilterRule',

    # Tasks
    'PaperlessTask',

    # UI settings
    'UiSettings',

    # Workflows
    'Workflow',
    'WorkflowTrigger',
    'WorkflowAction',
    'WorkflowActionEmail',
    'WorkflowActionWebhook',
    'WorkflowRun',

    # Thread-local tenant helpers
    'get_current_tenant_id',
    'set_current_tenant_id',
]
