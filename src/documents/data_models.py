import dataclasses
import datetime
import enum
from pathlib import Path
from typing import List
from typing import Optional

import magic


@dataclasses.dataclass
class DocumentMetadataOverrides:
    """
    Manages overrides for document fields which normally would
    be set from content or matching.  All fields default to None,
    meaning no override is happening
    """

    filename: Optional[str] = None
    title: Optional[str] = None
    correspondent_id: Optional[int] = None
    document_type_id: Optional[int] = None
    tag_ids: Optional[List[int]] = None
    created: Optional[datetime.datetime] = None
    asn: Optional[int] = None
    owner_id: Optional[int] = None


class DocumentSource(enum.IntEnum):
    """
    The source of an incoming document.  May have other uses in the future
    """

    ConsumeFolder = enum.auto()
    ApiUpload = enum.auto()
    MailFetch = enum.auto()


@dataclasses.dataclass
class ConsumableDocument:
    """
    Encapsulates an incoming document, either from consume folder, API upload
    or mail fetching and certain useful operations on it.
    """

    source: DocumentSource
    original_file: Path
    mime_type: str = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        """
        After a dataclass is initialized, this is called to finalize some data
        1. Make sure the original path is an absolute, fully qualified path
        2. Get the mime type of the file
        """
        # Always fully qualify the path first thing
        # Just in case, convert to a path if it's a str
        self.original_file = Path(self.original_file).resolve()

        # Get the file type once at init
        # Note this function isn't called when the object is unpickled
        self.mime_type = magic.from_file(self.original_file, mime=True)
