#!/usr/bin/env bash

echo "

A document with an id of ${DOCUMENT_ID} was just consumed.  I know the
following additional information about it:

* Generated File Name: ${DOCUMENT_FILE_NAME}
* Archive Path: ${DOCUMENT_ARCHIVE_PATH}
* Source Path: ${DOCUMENT_SOURCE_PATH}
* Created: ${DOCUMENT_CREATED}
* Added: ${DOCUMENT_ADDED}
* Modified: ${DOCUMENT_MODIFIED}
* Thumbnail Path: ${DOCUMENT_THUMBNAIL_PATH}
* Download URL: ${DOCUMENT_DOWNLOAD_URL}
* Thumbnail URL: ${DOCUMENT_THUMBNAIL_URL}
* Owner Name: ${DOCUMENT_OWNER}
* Correspondent: ${DOCUMENT_CORRESPONDENT}
* Tags: ${DOCUMENT_TAGS}

It was consumed with the passphrase ${PASSPHRASE}

"
