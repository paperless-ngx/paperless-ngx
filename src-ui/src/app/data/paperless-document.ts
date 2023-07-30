import { Observable } from 'rxjs'
import { ObjectWithPermissions } from './object-with-permissions'
import { PaperlessCorrespondent } from './paperless-correspondent'
import { PaperlessIndexFieldMetadata } from './paperless-document-index-field-metadata'
import { PaperlessDocumentNote } from './paperless-document-note'
import { PaperlessDocumentType } from './paperless-document-type'
import { PaperlessStoragePath } from './paperless-storage-path'
import { PaperlessTag } from './paperless-tag'

export interface SearchHit {
  score?: number
  rank?: number

  highlights?: string
  note_highlights?: string
}

export interface PaperlessDocument extends ObjectWithPermissions {
  correspondent$?: Observable<PaperlessCorrespondent>

  correspondent?: number

  document_type$?: Observable<PaperlessDocumentType>

  document_type?: number

  storage_path$?: Observable<PaperlessStoragePath>

  storage_path?: number

  title?: string

  content?: string

  tags$?: Observable<PaperlessTag[]>

  tags?: number[]

  checksum?: string

  // UTC
  created?: Date

  // localized date
  created_date?: Date

  modified?: Date

  added?: Date

  original_file_name?: string

  download_url?: string

  thumbnail_url?: string

  archive_serial_number?: number

  notes?: PaperlessDocumentNote[]

  metadatas?: PaperlessIndexFieldMetadata[]

  __search_hit__?: SearchHit
}
