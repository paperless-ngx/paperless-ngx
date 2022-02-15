import { PaperlessCorrespondent } from './paperless-correspondent'
import { ObjectWithId } from './object-with-id'
import { PaperlessTag } from './paperless-tag'
import { PaperlessDocumentType } from './paperless-document-type'
import { Observable } from 'rxjs'

export interface SearchHit {

  score?: number
  rank?: number

  highlights?: string

}

export interface PaperlessDocument extends ObjectWithId {

    correspondent$?: Observable<PaperlessCorrespondent>

    correspondent?: number

    document_type$?: Observable<PaperlessDocumentType>

    document_type?: number

    title?: string

    content?: string

    file_type?: string

    tags$?: Observable<PaperlessTag[]>

    tags?: number[]

    checksum?: string

    created?: Date

    modified?: Date

    added?: Date

    file_name?: string

    download_url?: string

    thumbnail_url?: string

    archive_serial_number?: number

    __search_hit__?: SearchHit

}
