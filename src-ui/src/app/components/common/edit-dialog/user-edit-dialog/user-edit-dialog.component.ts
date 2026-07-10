import { Component, OnInit, inject, signal } from '@angular/core'
import { toSignal } from '@angular/core/rxjs-interop'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { first, map } from 'rxjs'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { Group } from 'src/app/data/group'
import { User } from 'src/app/data/user'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmButtonComponent } from '../../confirm-button/confirm-button.component'
import { PasswordComponent } from '../../input/password/password.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { PermissionsSelectComponent } from '../../permissions-select/permissions-select.component'

@Component({
  selector: 'pngx-user-edit-dialog',
  templateUrl: './user-edit-dialog.component.html',
  styleUrls: ['./user-edit-dialog.component.scss'],
  imports: [
    PermissionsSelectComponent,
    SelectComponent,
    TextComponent,
    PasswordComponent,
    ConfirmButtonComponent,
    FormsModule,
    ReactiveFormsModule,
  ],
})
export class UserEditDialogComponent
  extends EditDialogComponent<User>
  implements OnInit
{
  private toastService = inject(ToastService)
  private readonly groupsService = inject(GroupService)

  readonly groups = toSignal(
    this.groupsService.listAll().pipe(map((result) => result.results)),
    { initialValue: undefined as Group[] }
  )
  readonly passwordIsSet = signal(false)
  readonly totpLoading = signal(false)

  constructor() {
    super()
    this.service = inject(UserService)
    this.settingsService = inject(SettingsService)
  }

  ngOnInit(): void {
    super.ngOnInit()
    this.onToggleSuperUser()
    if (!this.currentUserIsSuperUser) {
      this.objectForm.get('is_superuser').disable()
    } else {
      this.objectForm.get('is_superuser').enable()
    }
  }

  getCreateTitle() {
    return $localize`Create new user account`
  }

  getEditTitle() {
    return $localize`Edit user account`
  }

  getForm(): FormGroup {
    return new FormGroup({
      username: new FormControl(''),
      email: new FormControl(''),
      password: new FormControl(null),
      first_name: new FormControl(''),
      last_name: new FormControl(''),
      is_active: new FormControl(true),
      is_staff: new FormControl(true),
      is_superuser: new FormControl(false),
      groups: new FormControl([]),
      user_permissions: new FormControl([]),
    })
  }

  onToggleSuperUser() {
    if (this.objectForm.get('is_superuser').value) {
      this.objectForm.get('user_permissions').disable()
    } else {
      this.objectForm.get('user_permissions').enable()
    }
  }

  get inheritedPermissions(): string[] {
    const groupsVal: Array<number> = this.objectForm.get('groups').value

    if (!groupsVal) return []
    else
      return groupsVal.flatMap(
        (id) => this.groups()?.find((g) => g.id == id)?.permissions
      )
  }

  save(): void {
    this.passwordIsSet.set(
      this.objectForm.get('password').value?.toString().replaceAll('*', '')
        .length > 0
    )
    super.save()
  }

  get currentUserIsSuperUser(): boolean {
    return this.permissionsService.isSuperUser()
  }

  deactivateTotp() {
    this.totpLoading.set(true)
    ;(this.service as UserService)
      .deactivateTotp(this.object)
      .pipe(first())
      .subscribe({
        next: (result) => {
          this.totpLoading.set(false)
          if (result) {
            this.toastService.showInfo($localize`Totp deactivated`)
            this.object.is_mfa_enabled = false
          } else {
            this.toastService.showError($localize`Totp deactivation failed`)
          }
        },
        error: (e) => {
          this.totpLoading.set(false)
          this.toastService.showError($localize`Totp deactivation failed`, e)
        },
      })
  }
}
