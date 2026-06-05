import { ObjectWithPermissions } from './object-with-permissions'

export interface Folder extends ObjectWithPermissions {
  name?: string

  parent?: number // Folder ID

  children?: Folder[] // read-only, nested

  is_default?: boolean

  full_path?: string

  document_count?: number

  // UI only, computed during tree flattening
  depth?: number
}
