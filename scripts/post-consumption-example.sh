#!/usr/bin/env bash

PASSPHRASE=${1}
DOCUMENT_ID=${2}
DOCUMENT_FILE_NAME=${3}
DOCUMENT_SOURCE_PATH=${4}
DOCUMENT_THUMBNAIL_PATH=${5}
DOCUMENT_DOWNLOAD_URL=${6}
DOCUMENT_THUMBNAIL_URL=${7}
DOCUMENT_CORRESPONDENT=${8}
DOCUMENT_TAGS=${9}

echo "

A document with an id of ${DOCUMENT_ID} was just consumed.  I know the
following additional information about it:

* Generated File Name: ${DOCUMENT_FILE_NAME}
* Source Path: ${DOCUMENT_SOURCE_PATH}
* Thumbnail Path: ${DOCUMENT_THUMBNAIL_PATH}
* Download URL: ${DOCUMENT_DOWNLOAD_URL}
* Thumbnail URL: ${DOCUMENT_THUMBNAIL_URL}
* Correspondent: ${DOCUMENT_CORRESPONDENT}
* Tags: ${DOCUMENT_TAGS}

It was consumed with the passphrase ${PASSPHRASE}

"
