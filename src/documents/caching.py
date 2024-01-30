from typing import Final

CLASSIFIER_VERSION_KEY: Final[str] = "classifier_version"
CLASSIFIER_HASH_KEY: Final[str] = "classifier_hash"
CLASSIFIER_MODIFIED_KEY: Final[str] = "classifier_modified"

CACHE_1_MINUTE: Final[int] = 60
CACHE_5_MINUTES: Final[int] = 5 * CACHE_1_MINUTE
CACHE_50_MINUTES: Final[int] = 50 * CACHE_1_MINUTE


def get_suggestion_key(document_id: int) -> str:
    """
    Builds the key to store a document's suggestion data in the cache
    """
    return f"doc_{document_id}_suggest"


def get_metadata_key(document_id: int, is_archive: bool) -> str:
    """
    Builds the key to store a document's metadata data in the cache
    """
    return (
        f"doc_{document_id}_archive_metadata"
        if is_archive
        else f"doc_{document_id}_original_metadata"
    )


def get_thumbnail_modified_key(document_id: int) -> str:
    """
    Builds the key to store a thumbnail's timestamp
    """
    return f"doc_{document_id}_thumbnail_modified"
