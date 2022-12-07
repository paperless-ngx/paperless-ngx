import { Injectable } from '@angular/core'
import { ObjectWithPermissions } from '../data/object-with-permissions'
import { PaperlessUser } from '../data/paperless-user'

export enum PermissionAction {
  Add = 'add',
  View = 'view',
  Change = 'change',
  Delete = 'delete',
}

export enum PermissionType {
  Document = '%s_document',
  Tag = '%s_tag',
  Correspondent = '%s_correspondent',
  DocumentType = '%s_documenttype',
  StoragePath = '%s_storagepath',
  SavedView = '%s_savedview',
  PaperlessTask = '%s_paperlesstask',
  UISettings = '%s_uisettings',
  Comment = '%s_comment',
  MailAccount = '%s_mailaccount',
  MailRule = '%s_mailrule',
  User = '%s_user',
  Admin = '%s_logentry',
}

export interface PaperlessPermission {
  action: PermissionAction
  type: PermissionType
}

@Injectable({
  providedIn: 'root',
})
export class PermissionsService {
  private permissions: string[]
  private currentUser: PaperlessUser

  public initialize(permissions: string[], currentUser: PaperlessUser) {
    this.permissions = permissions
    this.currentUser = currentUser
  }

  public currentUserCan(permission: PaperlessPermission): boolean {
    return this.permissions.includes(this.getPermissionCode(permission))
  }

  public currentUserIsOwner(owner: PaperlessUser): boolean {
    return owner?.id === this.currentUser.id
  }

  public currentUserHasObjectPermissions(
    action: string,
    object: ObjectWithPermissions
  ): boolean {
    return (object.permissions[action] as Array<number>)?.includes(
      this.currentUser.id
    )
  }

  public getPermissionCode(permission: PaperlessPermission): string {
    return permission.type.replace('%s', permission.action)
  }

  public getPermissionKeys(permissionStr: string): {
    actionKey: string
    typeKey: string
  } {
    const matches = permissionStr.match(/(.+)_/)
    let typeKey
    let actionKey
    if (matches?.length > 0) {
      const action = matches[1]
      const actionIndex = Object.values(PermissionAction).indexOf(
        action as PermissionAction
      )
      if (actionIndex > -1) {
        actionKey = Object.keys(PermissionAction)[actionIndex]
      }
      const typeIndex = Object.values(PermissionType).indexOf(
        permissionStr.replace(action, '%s') as PermissionType
      )
      if (typeIndex > -1) {
        typeKey = Object.keys(PermissionType)[typeIndex]
      }
    }

    return { actionKey, typeKey }
  }
}
