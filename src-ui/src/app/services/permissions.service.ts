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
  Auth = 'auth.%s_user',
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
}
