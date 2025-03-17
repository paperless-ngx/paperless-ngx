import { Component } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { DocumentType } from 'src/app/data/document-type'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CustomField } from 'src/app/data/custom-field'
import { first } from 'rxjs'
import { CustomFieldsService } from '../../../../services/rest/custom-fields.service'

@Component({
  selector: 'pngx-document-type-edit-dialog',
  templateUrl: './document-type-edit-dialog.component.html',
  styleUrls: ['./document-type-edit-dialog.component.scss'],
})
export class DocumentTypeEditDialogComponent extends EditDialogComponent<DocumentType> {
  customFields: CustomField[]
  constructor(
    service: DocumentTypeService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService,
    customFieldsService: CustomFieldsService
  ) {
    super(service, activeModal, userService, settingsService)
    customFieldsService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.customFields = result.results))
  }

  getCreateTitle() {
    return $localize`Create new document type`
  }

  getEditTitle() {
    return $localize`Edit document type`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      custom_fields: new FormControl(),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
