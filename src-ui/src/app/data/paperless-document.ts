import { PaperlessCorrespondent } from './paperless-correspondent'
import { ObjectWithId } from './object-with-id'
import { PaperlessTag } from './paperless-tag'
import { PaperlessDocumentType } from './paperless-document-type'

export interface PaperlessDocument extends ObjectWithId {

    correspondent_object?: PaperlessCorrespondent

    correspondent?: number

    document_type_object?: PaperlessDocumentType

    document_type?: number

    title?: string

    content?: string

    file_type?: string

    tags_objects?: PaperlessTag[]

    tags?: number[]

    checksum?: string

    created?: Date

    modified?: Date

    added?: Date

    file_name?: string

    download_url?: string

    thumbnail_url?: string

    archive_serial_number?: number

}
