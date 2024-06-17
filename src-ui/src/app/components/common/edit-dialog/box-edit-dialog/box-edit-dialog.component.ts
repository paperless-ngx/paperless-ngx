import { Component } from '@angular/core';
import { Box } from 'src/app/data/box';
import { EditDialogComponent } from '../edit-dialog.component';
import { UserService } from 'src/app/services/rest/user.service';
import { SettingsService } from 'src/app/services/settings.service';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { FormControl, FormGroup } from '@angular/forms';
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model';
import { BoxService } from 'src/app/services/rest/box.service';

@Component({
  selector: 'pngx-box-edit-dialog',
  templateUrl: './box-edit-dialog.component.html',
  styleUrls: ['./box-edit-dialog.component.scss']
})
export class BoxEditDialogComponent extends EditDialogComponent<Box> {
  constructor(
    service: BoxService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  getCreateTitle() {
    return $localize`Create new Boxcase`
  }

  getEditTitle() {
    return $localize`Edit Boxcase`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      type: new FormControl('Boxcase'),
      parent_customfield: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}