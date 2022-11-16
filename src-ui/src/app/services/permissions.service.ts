import { Injectable } from '@angular/core'

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

  public initialize(permissions: string[]) {
    this.permissions = permissions
  }

  public currentUserCan(permission: PaperlessPermission): boolean {
    return this.permissions.includes(this.getPermissionCode(permission))
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
