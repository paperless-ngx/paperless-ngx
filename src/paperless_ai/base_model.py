from pydantic import BaseModel


class DocumentClassifierSchema(BaseModel):
    """Schema for document classification suggestions."""

    title: str
    tags: list[str]
    correspondents: list[str]
    document_types: list[str]
    storage_paths: list[str]
    dates: list[str]
