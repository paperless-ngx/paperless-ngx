import { ObjectWithId } from './object-with-id'
import { PaperlessUser } from './paperless-user'

export interface PermissionsObject {
  view: {
    users: Array<number>
    groups: Array<number>
  }
  change: {
    users: Array<number>
    groups: Array<number>
  }
}

export interface ObjectWithPermissions extends ObjectWithId {
  owner?: PaperlessUser

  permissions?: PermissionsObject
}
