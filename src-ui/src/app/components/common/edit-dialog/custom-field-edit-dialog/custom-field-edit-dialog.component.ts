import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import {
  DATA_TYPE_LABELS,
  PaperlessCustomField,
} from 'src/app/data/paperless-custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'

@Component({
  selector: 'pngx-custom-field-edit-dialog',
  templateUrl: './custom-field-edit-dialog.component.html',
  styleUrls: ['./custom-field-edit-dialog.component.scss'],
})
export class CustomFieldEditDialogComponent
  extends EditDialogComponent<PaperlessCustomField>
  implements OnInit
{
  constructor(
    service: CustomFieldsService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  ngOnInit(): void {
    super.ngOnInit()
    if (this.typeFieldDisabled) {
      this.objectForm.get('data_type').disable()
    }
  }

  getCreateTitle() {
    return $localize`Create new custom field`
  }

  getEditTitle() {
    return $localize`Edit custom field`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      data_type: new FormControl(null),
    })
  }

  getDataTypes() {
    return DATA_TYPE_LABELS
  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }
}
