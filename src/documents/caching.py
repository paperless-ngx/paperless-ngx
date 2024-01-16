from typing import Final

CLASSIFIER_VERSION_KEY: Final[str] = "classifier_version"
CLASSIFIER_HASH_KEY: Final[str] = "classifier_hash"
CLASSIFIER_MODIFIED_KEY: Final[str] = "classifier_modified"

CACHE_1_MINUTE: Final[int] = 60
CACHE_5_MINUTES: Final[int] = 5 * CACHE_1_MINUTE

DOC_SUGGESTIONS_BASE: Final[str] = "doc_{}_suggest"
DOC_METADATA_BASE: Final[str] = "doc_{}_metadata"
