import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'
import { Dossier } from 'src/app/data/dossier'
import { DossierService } from 'src/app/services/rest/dossier.service'

@Component({
  selector: 'pngx-dossier-edit-dialog',
  templateUrl: './dossier-edit-dialog.component.html',
  styleUrls: ['./dossier-edit-dialog.component.scss'],
})
export class DossierEditDialogComponent
  extends EditDialogComponent<Dossier>
  implements OnInit {
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
    if (this.typeFieldDisabled) {
    }
  }

  getCreateTitle() {
    return $localize`Create new dossier`
  }

  getEditTitle() {
    return $localize`Edit dossier`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      permissions_form: new FormControl(null),
    })
  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }
}
