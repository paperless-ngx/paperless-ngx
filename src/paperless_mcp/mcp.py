from mcp_server import ModelQueryToolset

from documents.models import Document


class DocumentQueryToolset(ModelQueryToolset):
    """
    Toolset for querying documents in the Paperless-ngx application.
    """

    model = Document

    def get_queryset(self):
        return super().get_queryset()
