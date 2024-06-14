import { ObjectWithPermissions } from './object-with-permissions'

export enum FileVersion {
  Archive = 'archive',
  Original = 'original',
}

export interface ShareLink extends ObjectWithPermissions {
  created: string // Date

  expiration?: string // Date

  slug: string

  document: number // Document

  file_version: string
}
