#!/usr/bin/env bash

DOCUMENT_FILE_NAME=${1}
DOCUMENT_SOURCE_PATH=${2}
DOCUMENT_THUMBNAIL_PATH=${3}
DOCUMENT_DOWNLOAD_URL=${4}
DOCUMENT_THUMBNAIL_URL=${5}
DOCUMENT_ID=${6}
DOCUMENT_CORRESPONDENT=${7}
DOCUMENT_TAGS=${8}

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

"
