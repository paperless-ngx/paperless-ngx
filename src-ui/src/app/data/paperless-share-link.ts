import { ObjectWithPermissions } from './object-with-permissions'

export enum PaperlessShareLinkDocumentVersion {
  Archive = 'archive',
  Original = 'original',
}

export interface PaperlessShareLink extends ObjectWithPermissions {
  created: string // Date

  expiration?: string // Date

  slug: string

  document: number // PaperlessDocument

  document_version: string
}
