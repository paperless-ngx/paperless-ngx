import { DecimalPipe } from '@angular/common'
import { Component, inject, Input, OnInit } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ToastService } from 'src/app/services/toast.service'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-email-document-dialog',
  templateUrl: './email-document-dialog.component.html',
  styleUrl: './email-document-dialog.component.scss',
  imports: [FormsModule, NgxBootstrapIconsModule, DecimalPipe],
})
export class EmailDocumentDialogComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  private activeModal = inject(NgbActiveModal)
  private documentService = inject(DocumentService)
  private toastService = inject(ToastService)

  @Input()
  documentIds: number[]

  @Input()
  totalOriginalSizeBytes: number = 0

  @Input()
  totalArchiveSizeBytes: number = 0

  private _hasArchiveVersion: boolean = true

  @Input()
  set hasArchiveVersion(value: boolean) {
    this._hasArchiveVersion = value
    this.useArchiveVersion = value
  }

  get hasArchiveVersion(): boolean {
    return this._hasArchiveVersion
  }

  public useArchiveVersion: boolean = true
  public showSizeWarning: boolean = false

  public emailAddress: string = ''
  public emailSubject: string = ''
  public emailMessage: string = ''

  get currentAttachmentSizeBytes(): number {
    return this.useArchiveVersion
      ? this.totalArchiveSizeBytes
      : this.totalOriginalSizeBytes
  }

  get currentAttachmentSizeMB(): number {
    return this.currentAttachmentSizeBytes / (1024 * 1024)
  }

  private updateSizeWarning() {
    const SIZE_WARNING_THRESHOLD_MB = 10
    this.showSizeWarning =
      this.currentAttachmentSizeMB > SIZE_WARNING_THRESHOLD_MB
  }

  constructor() {
    super()
    this.loading = false
  }

  ngOnInit() {
    this.updateSizeWarning()
  }

  onArchiveVersionToggle(value: boolean) {
    this.useArchiveVersion = value
    this.updateSizeWarning()
  }

  public emailDocuments() {
    this.loading = true
    this.documentService
      .emailDocuments(
        this.documentIds,
        this.emailAddress,
        this.emailSubject,
        this.emailMessage,
        this.useArchiveVersion
      )
      .subscribe({
        next: () => {
          this.loading = false
          this.emailAddress = ''
          this.emailSubject = ''
          this.emailMessage = ''
          this.close()
          const successMessage =
            this.documentIds.length > 1
              ? $localize`Documents emailed successfully`
              : $localize`Email sent`
          this.toastService.showInfo(successMessage)
        },
        error: (e) => {
          this.loading = false
          const errorMessage =
            this.documentIds.length > 1
              ? $localize`Error emailing documents`
              : $localize`Error emailing document`
          this.toastService.showError(errorMessage, e)
        },
      })
  }

  public close() {
    this.activeModal.close()
  }
}
