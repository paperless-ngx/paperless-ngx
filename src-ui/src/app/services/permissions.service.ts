import { Injectable } from '@angular/core'
import { ObjectWithPermissions } from '../data/object-with-permissions'
import { User } from '../data/user'
import { isString } from '@ng-bootstrap/ng-bootstrap/util/util'

export enum PermissionAction {
  Add = 'add',
  View = 'view',
  Change = 'change',
  Delete = 'delete',
}

export enum PermissionType {
  Document = '%s_document',
  Tag = '%s_tag',
  Warehouse = '%s_warehouse',
  Correspondent = '%s_correspondent',
  DocumentType = '%s_documenttype',
  StoragePath = '%s_storagepath',
  SavedView = '%s_savedview',
  PaperlessTask = '%s_paperlesstask',
  AppConfig = '%s_applicationconfiguration',
  UISettings = '%s_uisettings',
  Note = '%s_note',
  MailAccount = '%s_mailaccount',
  MailRule = '%s_mailrule',
  User = '%s_user',
  Group = '%s_group',
  ShareLink = '%s_sharelink',
  CustomField = '%s_customfield',
  Workflow = '%s_workflow',
  Approval = '%s_approval',
  Folder = '%s_folder',
  Dossier = '%s_dossier',
  DossierForm = '%s_dossierform'
}

export enum DevelopPermissionType {
  Document = '%s_document',
  Tag = '%s_tag',
  Warehouse = '%s_warehouse',
  // Correspondent = '%s_correspondent',
  DocumentType = '%s_documenttype',
  // StoragePath = '%s_storagepath',
  SavedView = '%s_savedview',
  PaperlessTask = '%s_paperlesstask',
  AppConfig = '%s_applicationconfiguration',
  UISettings = '%s_uisettings',
  Note = '%s_note',
  // MailAccount = '%s_mailaccount',
  // MailRule = '%s_mailrule',
  User = '%s_user',
  Group = '%s_group',
  ShareLink = '%s_sharelink',
  CustomField = '%s_customfield',
  Workflow = '%s_workflow',
  Approval = '%s_approval',
  Folder = '%s_folder',

}


@Injectable({
  providedIn: 'root',
})
export class PermissionsService {
  private permissions: string[]
  private currentUser: User

  public initialize(permissions: string[], currentUser: User) {
    this.permissions = permissions
    this.currentUser = currentUser
  }

  private isStringInEnum(v,enumPermissionType): boolean {
    return Object.values(enumPermissionType).includes(v);
  }

  public currentUserCan(
    action: PermissionAction,
    type: PermissionType
  ): boolean {
    if (!this.isStringInEnum(type,DevelopPermissionType))
    {
      return false;
    }
    return (
      this.currentUser?.is_superuser ||
      this.permissions?.includes(this.getPermissionCode(action, type))
    )
  }

  public isAdmin(): boolean {
    return this.currentUser?.is_staff
  }

  public currentUserOwnsObject(object: ObjectWithPermissions): boolean {
    return (
      !object ||
      !object.owner ||
      this.currentUser.is_superuser ||
      object.owner === this.currentUser.id
    )
  }

  getCurrentUser(){
    return this.currentUser
  }

  public currentUserHasObjectPermissions(
    action: string,
    object: ObjectWithPermissions
  ): boolean {
    if (action === PermissionAction.View) {
      return (
        this.currentUserOwnsObject(object) ||
        object.permissions?.view.users.includes(this.currentUser.id) ||
        object.permissions?.view.groups.filter((g) =>
          this.currentUser.groups.includes(g)
        ).length > 0
      )
    } else if (action === PermissionAction.Change) {
      return (
        this.currentUserOwnsObject(object) ||
        object.user_can_change ||
        object.permissions?.change.users.includes(this.currentUser.id) ||
        object.permissions?.change.groups.filter((g) =>
          this.currentUser.groups.includes(g)
        ).length > 0
      )
    }
  }

  public getPermissionCode(
    action: PermissionAction,
    type: PermissionType
  ): string {
    return type.replace('%s', action)
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
