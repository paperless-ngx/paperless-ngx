from pydantic import BaseModel
from pydantic import Field


class DocumentClassifierSchema(BaseModel):
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    correspondents: list[str] = Field(default_factory=list)
    document_types: list[str] = Field(default_factory=list)
    storage_paths: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
