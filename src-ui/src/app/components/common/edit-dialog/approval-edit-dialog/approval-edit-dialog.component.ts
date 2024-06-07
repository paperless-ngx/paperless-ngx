import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DATA_TYPE_LABELS,} from 'src/app/data/custom-field'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'
import { DocumentApproval } from 'src/app/data/document-approval'
import { DocumentApprovalsService } from 'src/app/services/rest/document-approvals.service'

@Component({
  selector: 'pngx-approval-edit-dialog',
  templateUrl: './approval-edit-dialog.component.html',
  styleUrls: ['./approval-edit-dialog.component.scss'],
})
export class ApprovalEditDialogComponent
  extends EditDialogComponent<DocumentApproval>
  implements OnInit
{
  constructor(
    service: DocumentApprovalsService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  ngOnInit(): void {
    super.ngOnInit()
    // if (this.typeFieldDisabled) {
    //   this.objectForm.get('data_type').disable()
    // }
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
