import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, Input, inject } from '@angular/core'
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  ShareBundleCreatePayload,
  ShareBundleSummary,
} from 'src/app/data/share-bundle'
import {
  FileVersion,
  SHARE_LINK_EXPIRATION_OPTIONS,
} from 'src/app/data/share-link'
import { FileSizePipe } from 'src/app/pipes/file-size.pipe'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component'

@Component({
  selector: 'pngx-share-bundle-dialog',
  templateUrl: './share-bundle-dialog.component.html',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
    FileSizePipe,
  ],
})
export class ShareBundleDialogComponent extends ConfirmDialogComponent {
  private formBuilder = inject(FormBuilder)
  private clipboard = inject(Clipboard)
  private toastService = inject(ToastService)

  private _documentIds: number[] = []

  selectionCount = 0
  documentPreview: number[] = []
  form: FormGroup = this.formBuilder.group({
    shareArchiveVersion: [true],
    expirationDays: [7],
  })
  payload: ShareBundleCreatePayload | null = null

  readonly expirationOptions = SHARE_LINK_EXPIRATION_OPTIONS

  createdBundle: ShareBundleSummary | null = null
  copied = false
  onOpenManage?: () => void
  readonly statusLabels: Record<ShareBundleSummary['status'], string> = {
    pending: $localize`Pending`,
    processing: $localize`Processing`,
    ready: $localize`Ready`,
    failed: $localize`Failed`,
  }
  readonly fileVersionLabels: Record<FileVersion, string> = {
    [FileVersion.Archive]: $localize`Archive`,
    [FileVersion.Original]: $localize`Original`,
  }

  constructor() {
    super()
    this.loading = false
    this.title = $localize`Share Selected Documents`
    this.btnCaption = $localize`Create`
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
    if (this.createdBundle) return
    this.payload = {
      document_ids: this.documentIds,
      file_version: this.form.value.shareArchiveVersion
        ? FileVersion.Archive
        : FileVersion.Original,
      expiration_days: this.form.value.expirationDays,
    }
    this.buttonsEnabled = false
    super.confirm()
  }

  getShareUrl(bundle: ShareBundleSummary): string {
    const apiURL = new URL(environment.apiBaseUrl)
    return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${
      bundle.slug
    }`
  }

  copy(bundle: ShareBundleSummary): void {
    const success = this.clipboard.copy(this.getShareUrl(bundle))
    if (success) {
      this.copied = true
      this.toastService.showInfo($localize`Share link copied to clipboard.`)
      setTimeout(() => {
        this.copied = false
      }, 3000)
    }
  }

  openManage(): void {
    if (this.onOpenManage) {
      this.onOpenManage()
    } else {
      this.cancel()
    }
  }

  statusLabel(status: ShareBundleSummary['status']): string {
    return this.statusLabels[status] ?? status
  }

  fileVersionLabel(version: FileVersion): string {
    return this.fileVersionLabels[version] ?? version
  }
}
