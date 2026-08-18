import { Injectable, signal } from '@angular/core'
import { ObjectWithPermissions } from '../data/object-with-permissions'
import { User } from '../data/user'

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
  AppConfig = '%s_applicationconfiguration',
  UISettings = '%s_uisettings',
  History = '%s_logentry',
  Note = '%s_note',
  MailAccount = '%s_mailaccount',
  MailRule = '%s_mailrule',
  User = '%s_user',
  Group = '%s_group',
  ShareLink = '%s_sharelink',
  ShareLinkBundle = '%s_sharelinkbundle',
  CustomField = '%s_customfield',
  Workflow = '%s_workflow',
  ExportTarget = '%s_exporttarget',
  ExportRecord = '%s_exportrecord',
  ProcessedMail = '%s_processedmail',
  GlobalStatistics = '%s_global_statistics',
  SystemMonitoring = '%s_system_monitoring',
}

@Injectable({
  providedIn: 'root',
})
export class PermissionsService {
  private permissions: string[]
  private currentUser: User
  private readonly permissionsVersion = signal(0)

  public initialize(permissions: string[], currentUser: User) {
    this.permissions = permissions
    this.currentUser = currentUser
    this.permissionsVersion.update((version) => version + 1)
  }

  public currentUserCan(
    action: PermissionAction,
    type: PermissionType
  ): boolean {
    this.permissionsVersion()
    return (
      this.currentUser?.is_superuser ||
      this.permissions?.includes(this.getPermissionCode(action, type))
    )
  }

  public isAdmin(): boolean {
    return this.currentUser?.is_staff
  }

  public isSuperUser(): boolean {
    return this.currentUser?.is_superuser
  }

  public currentUserOwnsObject(object: ObjectWithPermissions): boolean {
    return (
      !object ||
      !object.owner ||
      this.currentUser.is_superuser ||
      object.owner === this.currentUser.id
    )
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
    let typeKey
    let actionKey
    const actionIndex = Object.values(PermissionAction).findIndex((action) =>
      permissionStr.startsWith(`${action}_`)
    )
    if (actionIndex > -1) {
      const action = Object.values(PermissionAction)[actionIndex]
      actionKey = Object.keys(PermissionAction)[actionIndex]
      const typeIndex = Object.values(PermissionType).indexOf(
        permissionStr.replace(`${action}_`, '%s_') as PermissionType
      )
      if (typeIndex > -1) {
        typeKey = Object.keys(PermissionType)[typeIndex]
      }
    }

    return { actionKey, typeKey }
  }
}
