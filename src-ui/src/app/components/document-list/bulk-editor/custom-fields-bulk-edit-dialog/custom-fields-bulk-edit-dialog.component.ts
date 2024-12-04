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

  private _fieldsToAdd: CustomField[] = [] // static object for change detection
  public get fieldsToAdd() {
    return this._fieldsToAdd
  }

  private _fieldsToAddIds: number[] = []
  public get fieldsToAddIds() {
    return this._fieldsToAddIds
  }
  public set fieldsToAddIds(ids: number[]) {
    this._fieldsToAddIds = ids
    this._fieldsToAdd = this.customFields.filter((field) =>
      this._fieldsToAddIds.includes(field.id)
    )
    this.initForm()
  }

  public fieldsToRemoveIds: number[] = []

  public form: FormGroup = new FormGroup({})

  public documents: number[] = []

  constructor(
    private activeModal: NgbActiveModal,
    private documentService: DocumentService
  ) {}

  initForm() {
    Object.keys(this.form.controls).forEach((key) => {
      if (!this._fieldsToAddIds.includes(parseInt(key))) {
        this.form.removeControl(key)
      }
    })
    this._fieldsToAddIds.forEach((field_id) => {
      this.form.addControl(field_id.toString(), new FormControl(null))
    })
  }

  public save() {
    this.documentService
      .bulkEdit(this.documents, 'modify_custom_fields', {
        add_custom_fields: this.form.value,
        remove_custom_fields: this.fieldsToRemoveIds,
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
    this.fieldsToAddIds = this._fieldsToAddIds.filter((id) => id !== fieldId)
  }
}
