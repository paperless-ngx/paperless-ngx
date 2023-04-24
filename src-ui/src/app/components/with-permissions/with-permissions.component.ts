import {
  PermissionAction,
  PermissionType,
} from 'src/app/services/permissions.service'

export class ComponentWithPermissions {
  public readonly PermissionAction = PermissionAction
  public readonly PermissionType = PermissionType
}
