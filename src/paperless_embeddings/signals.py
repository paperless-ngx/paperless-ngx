def handle_document_save(sender, instance, created, **kwargs):
    """
    Generate embeddings when a document is saved
    """
    import logging

    logger = logging.getLogger("paperless.embedding")

    try:
        # Don't process if document is being created (it will be processed later)
        if created:
            return

        # Import here to avoid circular imports
        from django.conf import settings

        from paperless_embeddings.embedding import EmbeddingGenerator

        # Check if embeddings are enabled
        if not getattr(settings, "EMBEDDINGS_ENABLED", True):
            return

        # Get document ID and content
        document_id = instance.id
        content = instance.content

        if not content or not content.strip():
            logger.warning(
                f"Empty content for document {document_id}. Skipping embedding generation."
            )
            return

        # Create embedding generator
        embedding_generator = EmbeddingGenerator()

        # Extract relevant metadata
        metadata = {
            "filename": instance.filename or "",
            "title": instance.title or "",
            "date": str(instance.created) if instance.created else "",
            "mime_type": instance.mime_type or "",
            "correspondent": instance.correspondent.name
            if instance.correspondent
            else "",
            "document_type": instance.document_type.name
            if instance.document_type
            else "",
            "tags": ", ".join([tag.name for tag in instance.tags.all()])
            if instance.tags.exists()
            else "",
        }

        # Generate and store embeddings
        result = embedding_generator.generate_and_store_embeddings(
            document_id=document_id, text=content, metadata=metadata
        )

        if result:
            logger.info(f"Embeddings generated for document {document_id}")
        else:
            logger.warning(f"Failed to generate embeddings for document {document_id}")

    except Exception as e:
        # Log but don't block document save
        logger.error(f"Error generating document embeddings: {e}")


def handle_document_deletion(sender, instance, **kwargs):
    """
    Handle document deletion by removing embeddings from Redis
    """
    try:
        # Import here to avoid circular imports
        from paperless_embeddings.embedding import EmbeddingGenerator

        # Get document ID
        document_id = instance.id

        # Create embedding generator
        embedding_generator = EmbeddingGenerator()

        # Delete embeddings for the document
        embedding_generator.delete_document_embeddings(document_id)

    except Exception as e:
        # Log but don't block document deletion
        import logging

        logger = logging.getLogger("paperless.embedding")
        logger.error(f"Error deleting document embeddings: {e}")
