import { ObjectWithId } from './object-with-id'
import { PaperlessUser } from './paperless-user'

export interface ObjectWithPermissions extends ObjectWithId {
  user?: PaperlessUser

  permissions?: Array<[number, string]>
}
