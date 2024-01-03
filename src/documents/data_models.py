import dataclasses
import datetime
from enum import IntEnum
from pathlib import Path
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
    tag_ids: Optional[list[int]] = None
    storage_path_id: Optional[int] = None
    created: Optional[datetime.datetime] = None
    asn: Optional[int] = None
    owner_id: Optional[int] = None
    view_users: Optional[list[int]] = None
    view_groups: Optional[list[int]] = None
    change_users: Optional[list[int]] = None
    change_groups: Optional[list[int]] = None
    custom_field_ids: Optional[list[int]] = None

    def update(self, other: "DocumentMetadataOverrides") -> "DocumentMetadataOverrides":
        """
        Merges two DocumentMetadataOverrides objects such that object B's overrides
        are applied to object A or merged if multiple are accepted.

        The update is an in-place modification of self
        """
        # only if empty
        if other.title is not None:
            self.title = other.title
        if other.correspondent_id is not None:
            self.correspondent_id = other.correspondent_id
        if other.document_type_id is not None:
            self.document_type_id = other.document_type_id
        if other.storage_path_id is not None:
            self.storage_path_id = other.storage_path_id
        if other.owner_id is not None:
            self.owner_id = other.owner_id

        # merge
        if self.tag_ids is None:
            self.tag_ids = other.tag_ids
        elif other.tag_ids is not None:
            self.tag_ids.extend(other.tag_ids)
            self.tag_ids = list(set(self.tag_ids))

        if self.view_users is None:
            self.view_users = other.view_users
        elif other.view_users is not None:
            self.view_users.extend(other.view_users)
            self.view_users = list(set(self.view_users))

        if self.view_groups is None:
            self.view_groups = other.view_groups
        elif other.view_groups is not None:
            self.view_groups.extend(other.view_groups)
            self.view_groups = list(set(self.view_groups))

        if self.change_users is None:
            self.change_users = other.change_users
        elif other.change_users is not None:
            self.change_users.extend(other.change_users)
            self.change_users = list(set(self.change_users))

        if self.change_groups is None:
            self.change_groups = other.change_groups
        elif other.change_groups is not None:
            self.change_groups.extend(other.change_groups)
            self.change_groups = list(set(self.change_groups))

        if self.custom_field_ids is None:
            self.custom_field_ids = other.custom_field_ids
        elif other.custom_field_ids is not None:
            self.custom_field_ids.extend(other.custom_field_ids)
            self.custom_field_ids = list(set(self.custom_field_ids))

        return self


class DocumentSource(IntEnum):
    """
    The source of an incoming document.  May have other uses in the future
    """

    ConsumeFolder = 1
    ApiUpload = 2
    MailFetch = 3


@dataclasses.dataclass
class ConsumableDocument:
    """
    Encapsulates an incoming document, either from consume folder, API upload
    or mail fetching and certain useful operations on it.
    """

    source: DocumentSource
    original_file: Path
    mailrule_id: Optional[int] = None
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
