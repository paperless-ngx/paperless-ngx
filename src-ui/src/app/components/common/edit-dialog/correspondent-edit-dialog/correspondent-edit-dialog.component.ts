import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { Correspondent } from 'src/app/data/correspondent'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'pngx-correspondent-edit-dialog',
  templateUrl: './correspondent-edit-dialog.component.html',
  styleUrls: ['./correspondent-edit-dialog.component.scss'],
})
export class CorrespondentEditDialogComponent extends EditDialogComponent<Correspondent> {
  constructor(
    service: CorrespondentService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  getCreateTitle() {
    return $localize`Create new correspondent`
  }

  getEditTitle() {
    return $localize`Edit correspondent`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
