from llama_index.core.bridge.pydantic import BaseModel


class DocumentClassifierSchema(BaseModel):
    title: str
    tags: list[str]
    correspondents: list[str]
    document_types: list[str]
    storage_paths: list[str]
    dates: list[str]
