import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'
import { Dossier, DossierType } from 'src/app/data/dossier'
import { DossierService } from 'src/app/services/rest/dossier.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'

@Component({
  selector: 'pngx-dossier-custom-form-edit-dialog',
  templateUrl: './dossier-instance-customfield-form-edit-dialog.component.html',
  styleUrls: ['./dossier-instance-customfield-form-edit-dialog.component.scss'],
})
export class DossierCustomFieldFormEditDialogComponent
extends EditDialogComponent<Dossier>
  implements OnInit {
  // groups: Group[]
  passwordIsSet: boolean = false

  constructor(
    service: DossierService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }


  ngOnInit(): void {
    super.ngOnInit()
    this.onToggleSuperUser()
  }

  getCreateTitle() {
    return $localize`Create new dossier`
  }

  getEditTitle() {
    return $localize`Edit field dossier`
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

  // get inheritedPermissions(): string[] {
  //   const groupsVal: Array<number> = this.objectForm.get('groups').value

  //   if (!groupsVal) return []
  //   else
  //     return groupsVal.flatMap(
  //       (id) => this.groups.find((g) => g.id == id)?.permissions
  //     )
  // }

  save(): void {
    this.passwordIsSet =
      this.objectForm.get('password').value?.toString().replaceAll('*', '')
        .length > 0
    super.save()
  }
}
