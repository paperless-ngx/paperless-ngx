import { Correspondent } from './correspondent'
import { Tag } from './tag'
import { DocumentType } from './document-type'
import { Observable } from 'rxjs'
import { StoragePath } from './storage-path'
import { ObjectWithPermissions } from './object-with-permissions'
import { DocumentNote } from './document-note'
import { CustomFieldInstance } from './custom-field-instance'

export interface SearchHit {
  score?: number
  rank?: number

  highlights?: string
  note_highlights?: string
}

export interface Document extends ObjectWithPermissions {
  correspondent$?: Observable<Correspondent>

  correspondent?: number

  document_type$?: Observable<DocumentType>

  document_type?: number

  storage_path$?: Observable<StoragePath>

  storage_path?: number

  title?: string

  content?: string

  tags$?: Observable<Tag[]>

  tags?: number[]

  checksum?: string

  // UTC
  created?: Date

  // localized date
  created_date?: Date

  modified?: Date

  added?: Date

  original_file_name?: string

  archived_file_name?: string

  download_url?: string

  thumbnail_url?: string

  archive_serial_number?: number

  notes?: DocumentNote[]

  __search_hit__?: SearchHit

  custom_fields?: CustomFieldInstance[]

  // write-only field
  remove_inbox_tags?: boolean
}
