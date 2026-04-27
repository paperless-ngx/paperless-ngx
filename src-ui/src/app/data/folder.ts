import { ObjectWithPermissions } from './object-with-permissions'

export interface Folder extends ObjectWithPermissions {
  name: string
  parent?: number // parent folder ID, null = root
  children?: number[] // child folder IDs (read-only from API)
  document_count?: number
  full_path?: string
}
