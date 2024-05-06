import { Component, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { Group } from 'src/app/data/group'
import { User } from 'src/app/data/user'
import { GroupService } from 'src/app/services/rest/group.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'pngx-user-edit-dialog',
  templateUrl: './user-edit-dialog.component.html',
  styleUrls: ['./user-edit-dialog.component.scss'],
})
export class UserEditDialogComponent
  extends EditDialogComponent<User>
  implements OnInit
{
  groups: Group[]
  passwordIsSet: boolean = false

  constructor(
    service: UserService,
    activeModal: NgbActiveModal,
    groupsService: GroupService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, service, settingsService)

    groupsService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.groups = result.results))
  }

  ngOnInit(): void {
    super.ngOnInit()
    this.onToggleSuperUser()
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
        (id) => this.groups.find((g) => g.id == id)?.permissions
      )
  }

  save(): void {
    this.passwordIsSet =
      this.objectForm.get('password').value?.toString().replaceAll('*', '')
        .length > 0
    super.save()
  }
}
