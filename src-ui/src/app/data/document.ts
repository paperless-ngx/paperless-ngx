import { Correspondent } from './correspondent'
import { Tag } from './tag'
import { DocumentType } from './document-type'
import { ArchiveFont } from './archive-font'
import { Observable } from 'rxjs'
import { StoragePath } from './storage-path'
import { Warehouse } from './warehouse'
import { ObjectWithPermissions } from './object-with-permissions'
import { DocumentNote } from './document-note'
import { CustomFieldInstance } from './custom-field-instance'
import { DocumentApproval } from './document-approval'

export interface SearchHit {
  score?: number
  rank?: number

  highlights?: string
  note_highlights?: string
}

export interface Document extends ObjectWithPermissions {
  [x: string]: any
  correspondent$?: Observable<Correspondent>

  correspondent?: number

  document_type$?: Observable<DocumentType>

  document_type?: number

  archive_font$?: Observable<ArchiveFont>

  archive_font?: number

  storage_path$?: Observable<StoragePath>

  storage_path?: number

  warehouse$?: Observable<Warehouse>

  warehouse?: number

  warehouse_w$?: Observable<Warehouse>

  warehouse_w?: number

  warehouse_s$?: Observable<Warehouse>

  warehouse_s?: number

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

  approvals?: DocumentApproval[]

  __search_hit__?: SearchHit

  custom_fields?: CustomFieldInstance[]

  // write-only field
  remove_inbox_tags?: boolean

  exploit?: number
}
