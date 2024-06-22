import { Component } from '@angular/core';
import { EditCustomfieldComponent } from '../edit-dialog/edit-customfield/edit-customfield.component';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { UserService } from 'src/app/services/rest/user.service';
import { SettingsService } from 'src/app/services/settings.service';
import { CustomField } from 'src/app/data/custom-field';
import { FormControl, FormGroup } from '@angular/forms';
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model';
import { CustomFields } from 'src/app/data/customfields';
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service';


@Component({
  selector: 'pngx-custom-shelf-edit-dialog',
  templateUrl: './custom-shelf-edit-dialog.component.html',
  styleUrls: ['./custom-shelf-edit-dialog.component.scss']
})
export class CustomShelfEditDialogComponent extends EditCustomfieldComponent<CustomField> {
  constructor(
    service: CustomFieldsService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  getCreateTitle() {
    return $localize`Create new customfield`
  }

  getEditTitle() {
    return $localize`Edit customfield`
  }


  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      type: new FormControl('Shelf'),
      parent_warehouse: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}