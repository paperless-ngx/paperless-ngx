import { ObjectWithId } from './object-with-id'

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
  owner?: number

  permissions?: PermissionsObject

  user_can_change?: boolean

  is_shared_by_requester?: boolean
}
