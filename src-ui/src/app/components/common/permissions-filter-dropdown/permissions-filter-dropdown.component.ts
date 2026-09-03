import { _IdGenerator } from '@angular/cdk/a11y'
import { NgClass } from '@angular/common'
import {
  Component,
  EventEmitter,
  Input,
  Output,
  inject,
  signal,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgSelectComponent } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { first } from 'rxjs'
import { User } from 'src/app/data/user'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { ClearableBadgeComponent } from '../clearable-badge/clearable-badge.component'

export class PermissionsSelectionModel {
  readonly ownerFilter = signal(OwnerFilterType.NONE)
  readonly hideUnowned = signal(false)
  readonly userID = signal<number>(null)
  readonly includeUsers = signal<number[]>([])
  readonly excludeUsers = signal<number[]>([])

  clear() {
    this.ownerFilter.set(OwnerFilterType.NONE)
    this.userID.set(null)
    this.hideUnowned.set(false)
    this.includeUsers.set([])
    this.excludeUsers.set([])
  }
}

export enum OwnerFilterType {
  NONE = 0,
  SELF = 1,
  NOT_SELF = 2,
  OTHERS = 3,
  UNOWNED = 4,
  SHARED_BY_ME = 5,
}

@Component({
  selector: 'pngx-permissions-filter-dropdown',
  templateUrl: './permissions-filter-dropdown.component.html',
  styleUrls: ['./permissions-filter-dropdown.component.scss'],
  imports: [
    ClearableBadgeComponent,
    IfPermissionsDirective,
    FormsModule,
    ReactiveFormsModule,
    NgbDropdownModule,
    NgSelectComponent,
    NgClass,
    NgxBootstrapIconsModule,
  ],
})
export class PermissionsFilterDropdownComponent extends ComponentWithPermissions {
  permissionsService = inject(PermissionsService)
  private settingsService = inject(SettingsService)

  public OwnerFilterType = OwnerFilterType

  private readonly idGenerator = inject(_IdGenerator)
  public readonly dropdownMenuId = this.idGenerator.getId(
    'pngx-permissions-filter-dropdown-'
  )

  @Input()
  title: string

  @Input()
  disabled = false

  @Input()
  selectionModel: PermissionsSelectionModel

  @Output()
  ownerFilterSet = new EventEmitter<PermissionsSelectionModel>()

  readonly users = signal<User[]>([])

  get isActive(): boolean {
    return (
      this.selectionModel.ownerFilter() !== OwnerFilterType.NONE ||
      this.selectionModel.hideUnowned()
    )
  }

  get ownerFilterLabel(): string {
    if (
      this.selectionModel?.ownerFilter() !== OwnerFilterType.SELF ||
      this.selectionModel?.userID() === this.settingsService.currentUser()?.id
    ) {
      return $localize`My documents`
    }

    const username = this.getUsername(this.selectionModel?.userID())
    return username
      ? $localize`Owned by ${username}`
      : $localize`Owned by another user`
  }

  get ownerExclusionFilterLabel(): string {
    const excludedUsers = this.selectionModel?.excludeUsers() ?? []
    if (
      this.selectionModel?.ownerFilter() !== OwnerFilterType.NOT_SELF ||
      (excludedUsers.length === 1 &&
        excludedUsers[0] === this.settingsService.currentUser()?.id)
    ) {
      return $localize`Shared with me`
    }

    const usernames = excludedUsers
      .map((id) => this.getUsername(id))
      .filter(Boolean)
    if (usernames.length === excludedUsers.length && usernames.length > 0) {
      return $localize`Not owned by ${usernames.join(', ')}`
    }
    return excludedUsers.length === 1
      ? $localize`Not owned by another user`
      : $localize`Not owned by selected users`
  }

  get sharedByFilterLabel(): string {
    if (
      this.selectionModel?.ownerFilter() !== OwnerFilterType.SHARED_BY_ME ||
      this.selectionModel?.userID() === this.settingsService.currentUser()?.id
    ) {
      return $localize`Shared by me`
    }

    const username = this.getUsername(this.selectionModel?.userID())
    return username
      ? $localize`Shared by ${username}`
      : $localize`Shared by another user`
  }

  constructor() {
    const userService = inject(UserService)

    super()
    const permissionsService = this.permissionsService

    if (
      permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.User
      )
    ) {
      userService
        .listAll()
        .pipe(first())
        .subscribe({
          next: (result) => this.users.set(result.results),
        })
    }
  }

  reset() {
    this.selectionModel.clear()
    this.onChange()
  }

  setFilter(type: OwnerFilterType) {
    this.selectionModel.ownerFilter.set(type)
    if (this.selectionModel.ownerFilter() === OwnerFilterType.SELF) {
      this.selectionModel.includeUsers.set([])
      this.selectionModel.excludeUsers.set([])
      this.selectionModel.userID.set(this.settingsService.currentUser().id)
      this.selectionModel.hideUnowned.set(false)
    } else if (this.selectionModel.ownerFilter() === OwnerFilterType.NOT_SELF) {
      this.selectionModel.userID.set(null)
      this.selectionModel.includeUsers.set([])
      this.selectionModel.excludeUsers.set([
        this.settingsService.currentUser().id,
      ])
      this.selectionModel.hideUnowned.set(false)
    } else if (this.selectionModel.ownerFilter() === OwnerFilterType.NONE) {
      this.selectionModel.userID.set(null)
      this.selectionModel.includeUsers.set([])
      this.selectionModel.excludeUsers.set([])
      this.selectionModel.hideUnowned.set(false)
    } else if (
      this.selectionModel.ownerFilter() === OwnerFilterType.SHARED_BY_ME
    ) {
      this.selectionModel.userID.set(this.settingsService.currentUser()?.id)
      this.selectionModel.includeUsers.set([])
      this.selectionModel.excludeUsers.set([])
      this.selectionModel.hideUnowned.set(false)
    } else if (this.selectionModel.ownerFilter() === OwnerFilterType.UNOWNED) {
      this.selectionModel.userID.set(null)
      this.selectionModel.includeUsers.set([])
      this.selectionModel.excludeUsers.set([])
      this.selectionModel.hideUnowned.set(false)
    }
    this.onChange()
  }

  onChange() {
    this.ownerFilterSet.emit(this.selectionModel)
  }

  clearIncludeUsers() {
    this.selectionModel.includeUsers.set([])
    this.onUserSelect()
  }

  onUserSelect() {
    this.selectionModel.ownerFilter.set(
      this.selectionModel.includeUsers()?.length
        ? OwnerFilterType.OTHERS
        : OwnerFilterType.NONE
    )
    this.onChange()
  }

  private getUsername(userID: number): string {
    return this.users().find((user) => user.id === userID)?.username
  }
}
