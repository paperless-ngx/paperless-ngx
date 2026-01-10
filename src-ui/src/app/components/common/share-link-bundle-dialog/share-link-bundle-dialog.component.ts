import { Clipboard } from '@angular/cdk/clipboard'
import { CommonModule } from '@angular/common'
import { Component, Input, inject } from '@angular/core'
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Document } from 'src/app/data/document'
import {
  FileVersion,
  SHARE_LINK_EXPIRATION_OPTIONS,
} from 'src/app/data/share-link'
import {
  SHARE_LINK_BUNDLE_FILE_VERSION_LABELS,
  SHARE_LINK_BUNDLE_STATUS_LABELS,
  ShareLinkBundleCreatePayload,
  ShareLinkBundleStatus,
  ShareLinkBundleSummary,
} from 'src/app/data/share-link-bundle'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { FileSizePipe } from 'src/app/pipes/file-size.pipe'
import { ToastService } from 'src/app/services/toast.service'
import { environment } from 'src/environments/environment'
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component'

@Component({
  selector: 'pngx-share-link-bundle-dialog',
  templateUrl: './share-link-bundle-dialog.component.html',
  imports: [
    CommonModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
    FileSizePipe,
    DocumentTitlePipe,
  ],
  providers: [],
})
export class ShareLinkBundleDialogComponent extends ConfirmDialogComponent {
  private readonly formBuilder = inject(FormBuilder)
  private readonly clipboard = inject(Clipboard)
  private readonly toastService = inject(ToastService)

  private _documents: Document[] = []

  selectionCount = 0
  documentPreview: Document[] = []
  form: FormGroup = this.formBuilder.group({
    shareArchiveVersion: true,
    expirationDays: [7],
  })
  payload: ShareLinkBundleCreatePayload | null = null

  readonly expirationOptions = SHARE_LINK_EXPIRATION_OPTIONS

  createdBundle: ShareLinkBundleSummary | null = null
  copied = false
  onOpenManage?: () => void
  readonly statuses = ShareLinkBundleStatus

  constructor() {
    super()
    this.loading = false
    this.title = $localize`Create share link bundle`
    this.btnCaption = $localize`Create link`
  }

  @Input()
  set documents(docs: Document[]) {
    this._documents = docs.concat()
    this.selectionCount = this._documents.length
    this.documentPreview = this._documents.slice(0, 10)
  }

  submit() {
    if (this.createdBundle) return
    this.payload = {
      document_ids: this._documents.map((doc) => doc.id),
      file_version: this.form.value.shareArchiveVersion
        ? FileVersion.Archive
        : FileVersion.Original,
      expiration_days: this.form.value.expirationDays,
    }
    this.buttonsEnabled = false
    super.confirm()
  }

  getShareUrl(bundle: ShareLinkBundleSummary): string {
    const apiURL = new URL(environment.apiBaseUrl)
    return `${apiURL.origin}${apiURL.pathname.replace(/\/api\/$/, '/share/')}${
      bundle.slug
    }`
  }

  copy(bundle: ShareLinkBundleSummary): void {
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

  statusLabel(status: ShareLinkBundleSummary['status']): string {
    return SHARE_LINK_BUNDLE_STATUS_LABELS[status] ?? status
  }

  fileVersionLabel(version: FileVersion): string {
    return SHARE_LINK_BUNDLE_FILE_VERSION_LABELS[version] ?? version
  }
}
