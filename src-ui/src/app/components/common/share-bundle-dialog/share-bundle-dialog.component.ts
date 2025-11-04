import { CommonModule } from '@angular/common'
import { Component, Input, inject } from '@angular/core'
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms'
import { ShareBundleCreatePayload } from 'src/app/data/share-bundle'
import {
  FileVersion,
  SHARE_LINK_EXPIRATION_OPTIONS,
} from 'src/app/data/share-link'
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component'

@Component({
  selector: 'pngx-share-bundle-dialog',
  templateUrl: './share-bundle-dialog.component.html',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
})
export class ShareBundleDialogComponent extends ConfirmDialogComponent {
  private formBuilder = inject(FormBuilder)

  private _documentIds: number[] = []

  selectionCount = 0
  documentPreview: number[] = []
  form: FormGroup = this.formBuilder.group({
    shareArchiveVersion: [true],
    expirationDays: [7],
  })
  payload: ShareBundleCreatePayload | null = null

  readonly expirationOptions = SHARE_LINK_EXPIRATION_OPTIONS

  constructor() {
    super()
    this.loading = false
    this.title = $localize`Share Selected Documents`
  }

  @Input()
  set documentIds(ids: number[]) {
    this._documentIds = ids ?? []
    this.selectionCount = this._documentIds.length
    this.documentPreview = this._documentIds.slice(0, 10)
  }

  get documentIds(): number[] {
    return this._documentIds
  }

  submit() {
    this.payload = {
      document_ids: this.documentIds,
      file_version: this.form.value.shareArchiveVersion
        ? FileVersion.Archive
        : FileVersion.Original,
      expiration_days: this.form.value.expirationDays,
    }
    super.confirm()
  }
}
