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
  built_at?: string
  size_bytes?: number
  last_error?: string
}

export interface ShareBundleCreatePayload {
  document_ids: number[]
  file_version: FileVersion
  expiration_days: number | null
}

export const SHARE_BUNDLE_STATUS_LABELS: Record<ShareBundleStatus, string> = {
  [ShareBundleStatus.Pending]: $localize`Pending`,
  [ShareBundleStatus.Processing]: $localize`Processing`,
  [ShareBundleStatus.Ready]: $localize`Ready`,
  [ShareBundleStatus.Failed]: $localize`Failed`,
}

export const SHARE_BUNDLE_FILE_VERSION_LABELS: Record<FileVersion, string> = {
  [FileVersion.Archive]: $localize`Archive`,
  [FileVersion.Original]: $localize`Original`,
}
