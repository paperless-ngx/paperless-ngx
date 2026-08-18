import { ObjectWithId } from './object-with-id'

export enum ExportRecordStatus {
  Pending = 'pending',
  Complete = 'complete',
  Failed = 'failed',
}

export interface ExportRecord extends ObjectWithId {
  target: number // ExportTarget.id

  target_name?: string

  action?: number

  document?: number

  document_pk: number

  status: ExportRecordStatus

  object_key: string

  checksum: string

  size_bytes?: number

  created_at: string // Date

  finished_at?: string // Date

  last_error?: { error?: string; attempt?: number }
}
