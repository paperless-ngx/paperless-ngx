import { CommonModule } from '@angular/common'
import { Component, Input, inject } from '@angular/core'
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import {
  FileVersion,
  SHARE_LINK_EXPIRATION_OPTIONS,
} from 'src/app/data/share-link'

@Component({
  selector: 'pngx-share-bundle-dialog',
  templateUrl: './share-bundle-dialog.component.html',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
})
export class ShareBundleDialogComponent {
  private activeModal = inject(NgbActiveModal)
  private formBuilder = inject(FormBuilder)

  private _documentIds: number[] = []
  private _documentsWithArchive = 0

  selectionCount = 0
  documentPreview: number[] = []
  form: FormGroup = this.formBuilder.group({
    shareArchiveVersion: [true],
    expirationDays: [7],
  })

  readonly expirationOptions = SHARE_LINK_EXPIRATION_OPTIONS

  @Input()
  set documentIds(ids: number[]) {
    this._documentIds = ids ?? []
    this.selectionCount = this._documentIds.length
    this.documentPreview = this._documentIds.slice(0, 10)
    this.syncArchiveOption()
  }

  get documentIds(): number[] {
    return this._documentIds
  }

  @Input()
  set documentsWithArchive(count: number) {
    this._documentsWithArchive = count ?? 0
    this.syncArchiveOption()
  }

  get documentsWithArchive(): number {
    return this._documentsWithArchive
  }

  get archiveOptionDisabled(): boolean {
    return (
      this.selectionCount === 0 ||
      this._documentsWithArchive !== this.selectionCount
    )
  }

  get missingArchiveCount(): number {
    return Math.max(this.selectionCount - this._documentsWithArchive, 0)
  }

  close() {
    this.activeModal.close()
  }

  submit() {
    // Placeholder until the backend workflow is wired up.
    this.activeModal.close({
      documentIds: this.documentIds,
      options: {
        fileVersion: this.form.value.shareArchiveVersion
          ? FileVersion.Archive
          : FileVersion.Original,
        expirationDays: this.form.value.expirationDays,
      },
    })
  }

  private syncArchiveOption() {
    const control = this.form.get('shareArchiveVersion')
    if (!control) return

    const canUseArchive =
      this.selectionCount > 0 &&
      this._documentsWithArchive === this.selectionCount

    if (canUseArchive) {
      control.enable({ emitEvent: false })
      control.patchValue(true, { emitEvent: false })
    } else {
      control.disable({ emitEvent: false })
      control.patchValue(false, { emitEvent: false })
    }
  }
}
