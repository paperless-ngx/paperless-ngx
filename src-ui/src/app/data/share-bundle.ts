import { FileVersion } from './share-link'

export enum ShareBundleStatus {
  Pending = 'pending',
  Processing = 'processing',
  Ready = 'ready',
  Failed = 'failed',
}

export interface ShareBundleSummary {
  id: number
  slug: string
  created: string // Date
  expiration?: string // Date
  documents: number[]
  document_count: number
  file_version: FileVersion
  status: ShareBundleStatus
  size_bytes?: number
  last_error?: string
}

export interface ShareBundleCreatePayload {
  document_ids: number[]
  file_version: FileVersion
  expiration_days: number | null
}
