import { PaperlessCorrespondent } from './paperless-correspondent'
import { PaperlessTag } from './paperless-tag'
import { PaperlessDocumentType } from './paperless-document-type'
import { Observable } from 'rxjs'
import { PaperlessStoragePath } from './paperless-storage-path'
import { ObjectWithPermissions } from './object-with-permissions'
import { PaperlessDocumentNote } from './paperless-document-note'

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

  __search_hit__?: SearchHit
}
