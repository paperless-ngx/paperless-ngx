import { ObjectWithPermissions } from './object-with-permissions'

export interface NamedCounter extends ObjectWithPermissions {
  name: string
  document_count?: number
}
