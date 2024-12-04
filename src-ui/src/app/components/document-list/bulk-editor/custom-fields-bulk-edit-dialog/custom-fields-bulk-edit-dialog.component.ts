import { Component, EventEmitter, Output } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { DocumentService } from 'src/app/services/rest/document.service'

@Component({
  selector: 'pngx-custom-fields-bulk-edit-dialog',
  templateUrl: './custom-fields-bulk-edit-dialog.component.html',
  styleUrl: './custom-fields-bulk-edit-dialog.component.scss',
})
export class CustomFieldsBulkEditDialogComponent {
  CustomFieldDataType = CustomFieldDataType

  @Output()
  succeeded = new EventEmitter()

  @Output()
  failed = new EventEmitter()

  public networkActive = false

  public customFields: CustomField[] = []

  private _selectedFields: CustomField[] = [] // static object for change detection
  public get selectedFields() {
    return this._selectedFields
  }

  private _selectedFieldsIds: number[] = []
  public get selectedFieldsIds() {
    return this._selectedFieldsIds
  }
  public set selectedFieldsIds(ids: number[]) {
    this._selectedFieldsIds = ids
    this._selectedFields = this.customFields.filter((field) =>
      this._selectedFieldsIds.includes(field.id)
    )
    this.initForm()
  }

  public form: FormGroup = new FormGroup({})

  public documents: number[]

  constructor(
    private activeModal: NgbActiveModal,
    private documentService: DocumentService
  ) {}

  initForm() {
    this.form = new FormGroup({})
    this._selectedFieldsIds.forEach((field_id) => {
      this.form.addControl(field_id.toString(), new FormControl(null))
    })
  }

  public save() {
    this.documentService
      .bulkEdit(this.documents, 'modify_custom_fields', {
        add_custom_fields: this.form.value,
        remove_custom_fields: [],
      })
      .pipe(first())
      .subscribe({
        next: () => {
          this.activeModal.close()
          this.succeeded.emit()
        },
        error: (error) => {
          this.failed.emit(error)
        },
      })
  }

  public cancel() {
    this.activeModal.close()
  }

  public removeField(fieldId: number) {
    this.selectedFieldsIds = this._selectedFieldsIds.filter(
      (id) => id !== fieldId
    )
  }
}
