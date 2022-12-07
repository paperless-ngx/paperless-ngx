import { ObjectWithId } from './object-with-id'
import { PaperlessUser } from './paperless-user'

export interface ObjectWithPermissions extends ObjectWithId {
  owner?: PaperlessUser

  permissions?: Array<[number, string]>
}
