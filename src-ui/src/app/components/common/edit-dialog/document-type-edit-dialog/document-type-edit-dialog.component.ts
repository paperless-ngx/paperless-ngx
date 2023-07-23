import { Component, OnInit } from '@angular/core'
import { FormArray, FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model'
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { UserService } from 'src/app/services/rest/user.service'
import { v4 as uuidv4 } from 'uuid'

@Component({
  selector: 'app-document-type-edit-dialog',
  templateUrl: './document-type-edit-dialog.component.html',
  styleUrls: ['./document-type-edit-dialog.component.scss'],
})
export class DocumentTypeEditDialogComponent
  extends EditDialogComponent<PaperlessDocumentType>
  implements OnInit
{
  constructor(
    service: DocumentTypeService,
    activeModal: NgbActiveModal,
    userService: UserService
  ) {
    super(service, activeModal, userService)
  }

  ngOnInit(): void {
    if (this.object != null) {
      const arr = this.objectForm.get('default_metadata') as FormArray
      this.object['default_metadata'].forEach((inf) =>
        arr.push(
          new FormGroup({
            id: new FormControl(inf.id),
            name: new FormControl(inf.name),
            displayName: new FormControl(inf.displayName),
            value: new FormControl(inf.value),
          })
        )
      )
    }
  }

  get indexFields() {
    return this.objectForm.value.default_metadata ?? []
  }

  trackIndexField(_: number, indexField: any) {
    return indexField.id
  }

  addIndexField() {
    const arr = this.objectForm.get('default_metadata') as FormArray
    console.log('arr:', arr)
    arr.push(
      new FormGroup({
        id: new FormControl(uuidv4()),
        name: new FormControl(''),
        displayName: new FormControl(''),
        value: new FormControl(''),
      })
    )
  }

  deleteIndexField(index: number) {
    const arr = this.objectForm.get('default_metadata') as FormArray
    arr.removeAt(index)
  }

  updateField(index: number, property: string, value: string) {
    const arr = this.objectForm.get('default_metadata') as FormArray
    arr.at(index).patchValue({ [property]: value })
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
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
      default_metadata: new FormArray([]),
    })
  }
}
