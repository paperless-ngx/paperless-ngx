import { Component, OnInit } from '@angular/core'
import { FormGroup, FormControl } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DATA_TYPE_LABELS } from 'src/app/data/custom-field'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'
import {
  DocumentApproval,
  EdocApprovalAccessType,
} from 'src/app/data/document-approval'
import { DocumentApprovalsService } from 'src/app/services/rest/document-approvals.service'
import { Group } from 'src/app/data/group'
import { GroupService } from 'src/app/services/rest/group.service'
import { first } from 'rxjs'
import { ApprovalsService } from 'src/app/services/rest/approval.service'

@Component({
  selector: 'pngx-approval-edit-dialog',
  templateUrl: './approval-edit-dialog.component.html',
  styleUrls: ['./approval-edit-dialog.component.scss'],
})
export class ApprovalEditDialogComponent
  extends EditDialogComponent<DocumentApproval>
  implements OnInit
{
  APPROVAL_ACCESS_TYPES_OPTIONS = [
    // {
    //   label: $localize`Owner`,
    //   value: PaperlessApprovalAccessType.Owner,
    // },
    // {
    //   label: $localize`Edit`,
    //   value: PaperlessApprovalAccessType.Edit,
    // },
    {
      label: $localize`View`,
      value: EdocApprovalAccessType.View,
    },
  ]

  EXPIRATION_OPTIONS = [
    { label: $localize`1 day`, value: 1 },
    { label: $localize`7 days`, value: 7 },
    { label: $localize`30 days`, value: 30 },
    { label: $localize`Never`, value: null },
  ]
  defaultAccessType = EdocApprovalAccessType.View;
  defaultExpiration: number = null
  expiration: number = 7
  groups: Group[]
  constructor(
    service: ApprovalsService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService,
    groupService: GroupService
  ) {
    super(service, activeModal, userService, settingsService)
    groupService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.groups = result.results))
  }

  ngOnInit(): void {
    super.ngOnInit()
    this.objectForm = this.getForm()
  }

  getCreateTitle() {
    return $localize`Create exploitation request`
  }

  getEditTitle() {
    return $localize`Create exploitation request`
  }

  getForm(): FormGroup {
    return new FormGroup({
      object_pk: new FormControl(this.object?.object_pk),
      expiration: new FormControl(this.defaultExpiration),
      ctype_id: new FormControl(this.object?.ctype),
      access_type: new FormControl(this.defaultAccessType),
      submitted_by_group: new FormControl([]),
    })
  }

  getDataTypes() {
    return DATA_TYPE_LABELS
  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }
  save(): void {
    const expirationDays = this.objectForm.get('expiration')?.value;
    if (expirationDays){
      let expirationDate = new Date();
      expirationDate.setDate(expirationDate.getDate() + (expirationDays || 0));
      this.objectForm.patchValue({
        expiration: expirationDate,
      });
    }

    // Gọi phương thức save() của lớp cha
    super.save();
  }
}
