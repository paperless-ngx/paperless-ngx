import { FileVersion } from './share-link'

export enum ShareLinkBundleStatus {
  Pending = 'pending',
  Processing = 'processing',
  Ready = 'ready',
  Failed = 'failed',
}

export type ShareLinkBundleError = {
  bundle_id: number
  message?: string
  exception_type?: string
  timestamp?: string
}

export interface ShareLinkBundleSummary {
  id: number
  slug: string
  created: string // Date
  expiration?: string // Date
  documents: number[]
  document_count: number
  file_version: FileVersion
  status: ShareLinkBundleStatus
  built_at?: string
  size_bytes?: number
  last_error?: ShareLinkBundleError
}

export interface ShareLinkBundleCreatePayload {
  document_ids: number[]
  file_version: FileVersion
  expiration_days: number | null
}

export const SHARE_LINK_BUNDLE_STATUS_LABELS: Record<
  ShareLinkBundleStatus,
  string
> = {
  [ShareLinkBundleStatus.Pending]: $localize`Pending`,
  [ShareLinkBundleStatus.Processing]: $localize`Processing`,
  [ShareLinkBundleStatus.Ready]: $localize`Ready`,
  [ShareLinkBundleStatus.Failed]: $localize`Failed`,
}

export const SHARE_LINK_BUNDLE_FILE_VERSION_LABELS: Record<
  FileVersion,
  string
> = {
  [FileVersion.Archive]: $localize`Archive`,
  [FileVersion.Original]: $localize`Original`,
}
