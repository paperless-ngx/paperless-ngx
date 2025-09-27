import { Component, Input, inject } from '@angular/core'
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
  imports: [FormsModule, NgxBootstrapIconsModule],
})
export class EmailDocumentDialogComponent extends LoadingComponentWithPermissions {
  private activeModal = inject(NgbActiveModal)
  private documentService = inject(DocumentService)
  private toastService = inject(ToastService)

  @Input()
  documentIds: number[]

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

  public emailAddress: string = ''
  public emailSubject: string = ''
  public emailMessage: string = ''

  constructor() {
    super()
    this.loading = false
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
          this.toastService.showInfo($localize`Email sent`)
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
