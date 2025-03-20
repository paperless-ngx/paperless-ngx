import { Component, EventEmitter, Output } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { first } from 'rxjs'
import { CheckComponent } from 'src/app/components/common/input/check/check.component'
import { DateComponent } from 'src/app/components/common/input/date/date.component'
import { DocumentLinkComponent } from 'src/app/components/common/input/document-link/document-link.component'
import { MonetaryComponent } from 'src/app/components/common/input/monetary/monetary.component'
import { NumberComponent } from 'src/app/components/common/input/number/number.component'
import { SelectComponent } from 'src/app/components/common/input/select/select.component'
import { TextComponent } from 'src/app/components/common/input/text/text.component'
import { UrlComponent } from 'src/app/components/common/input/url/url.component'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { DocumentService } from 'src/app/services/rest/document.service'

@Component({
  selector: 'pngx-custom-fields-bulk-edit-dialog',
  templateUrl: './custom-fields-bulk-edit-dialog.component.html',
  styleUrl: './custom-fields-bulk-edit-dialog.component.scss',
  imports: [
    CheckComponent,
    DateComponent,
    DocumentLinkComponent,
    MonetaryComponent,
    NumberComponent,
    SelectComponent,
    TextComponent,
    UrlComponent,
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
  ],
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
