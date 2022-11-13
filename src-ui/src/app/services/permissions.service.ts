import { Injectable } from '@angular/core'

export enum PermissionAction {
  Add = 'add',
  View = 'view',
  Change = 'change',
  Delete = 'delete',
}

export enum PermissionType {
  Document = 'documents.%s_document',
  Tag = 'documents.%s_tag',
  Correspondent = 'documents.%s_correspondent',
  DocumentType = 'documents.%s_documenttype',
  StoragePath = 'documents.%s_storagepath',
  SavedView = 'documents.%s_savedview',
  PaperlessTask = 'documents.%s_paperlesstask',
  UISettings = 'documents.%s_uisettings',
  Comment = 'documents.%s_comment',
  Log = 'admin.%s_logentry',
  MailAccount = 'paperless_mail.%s_mailaccount',
  MailRule = 'paperless_mail.%s_mailrule',
  User = 'auth.%s_user',
  Admin = 'admin.%s_logentry',
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

  private getPermissionCode(permission: PaperlessPermission): string {
    return permission.type.replace('%s', permission.action)
  }

  public getPermissionKeys(permissionStr: string): {
    actionKey: string
    typeKey: string
  } {
    const matches = permissionStr.match(/\.(.+)_/)
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
