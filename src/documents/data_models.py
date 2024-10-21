import dataclasses
import datetime
from enum import IntEnum
from pathlib import Path

import magic
from guardian.shortcuts import get_groups_with_perms
from guardian.shortcuts import get_users_with_perms


@dataclasses.dataclass
class DocumentMetadataOverrides:
    """
    Manages overrides for document fields which normally would
    be set from content or matching.  All fields default to None,
    meaning no override is happening
    """

    filename: str | None = None
    title: str | None = None
    correspondent_id: int | None = None
    document_type_id: int | None = None
    tag_ids: list[int] | None = None
    storage_path_id: int | None = None
    created: datetime.datetime | None = None
    asn: int | None = None
    owner_id: int | None = None
    view_users: list[int] | None = None
    view_groups: list[int] | None = None
    change_users: list[int] | None = None
    change_groups: list[int] | None = None
    custom_field_ids: list[int] | None = None

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

    @staticmethod
    def from_document(doc) -> "DocumentMetadataOverrides":
        """
        Fills in the overrides from a document object
        """
        overrides = DocumentMetadataOverrides()
        overrides.title = doc.title
        overrides.correspondent_id = doc.correspondent.id if doc.correspondent else None
        overrides.document_type_id = doc.document_type.id if doc.document_type else None
        overrides.storage_path_id = doc.storage_path.id if doc.storage_path else None
        overrides.owner_id = doc.owner.id if doc.owner else None
        overrides.tag_ids = list(doc.tags.values_list("id", flat=True))

        overrides.view_users = list(
            get_users_with_perms(
                doc,
                only_with_perms_in=["view_document"],
            ).values_list("id", flat=True),
        )
        overrides.change_users = list(
            get_users_with_perms(
                doc,
                only_with_perms_in=["change_document"],
            ).values_list("id", flat=True),
        )
        overrides.custom_field_ids = list(
            doc.custom_fields.values_list("field", flat=True),
        )

        groups_with_perms = get_groups_with_perms(
            doc,
            attach_perms=True,
        )
        overrides.view_groups = [
            group.id
            for group in groups_with_perms
            if "view_document" in groups_with_perms[group]
        ]
        overrides.change_groups = [
            group.id
            for group in groups_with_perms
            if "change_document" in groups_with_perms[group]
        ]

        return overrides


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
    mailrule_id: int | None = None
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
