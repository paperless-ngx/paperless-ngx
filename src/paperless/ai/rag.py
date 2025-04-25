from documents.models import Document
from paperless.ai.indexing import query_similar_documents


def get_context_for_document(doc: Document, max_docs: int = 5) -> str:
    similar_docs = query_similar_documents(doc)[:max_docs]
    context_blocks = []
    for similar in similar_docs:
        text = similar.content or ""
        title = similar.title or similar.filename or "Untitled"
        context_blocks.append(f"TITLE: {title}\n{text}")
    return "\n\n".join(context_blocks)
