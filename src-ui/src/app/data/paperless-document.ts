import { PaperlessCorrespondent } from './paperless-correspondent'
import { ObjectWithId } from './object-with-id'
import { PaperlessTag } from './paperless-tag'
import { PaperlessDocumentType } from './paperless-document-type'

export interface PaperlessDocument extends ObjectWithId {

    correspondent?: PaperlessCorrespondent

    correspondent_id?: number

    document_type?: PaperlessDocumentType

    document_type_id?: number

    title?: string

    content?: string

    file_type?: string

    tags?: PaperlessTag[]

    tags_id?: number[]

    checksum?: string

    created?: Date

    modified?: Date

    added?: Date

    file_name?: string

    download_url?: string

    thumbnail_url?: string

    archive_serial_number?: number

}
