import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { Warehouse } from 'src/app/data/warehouse'


import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { WarehouseService } from 'src/app/services/rest/warehouse.service'

@Component({
  selector: 'pngx-warehouse-edit-dialog',
  templateUrl: './warehouse-edit-dialog.component.html',
  styleUrls: ['./warehouse-edit-dialog.component.scss'],
})
export class WarehouseEditDialogComponent extends EditDialogComponent<Warehouse> {
  constructor(
    service: WarehouseService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  getCreateTitle() {
    return $localize`Create new warehouse`
  }

  getEditTitle() {
    return $localize`Edit warehouse`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      // document_count: new FormControl(''),
      type: new FormControl('Warehouse'),
      parent_warehouse: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
