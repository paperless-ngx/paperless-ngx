import { Component, Input } from '@angular/core'
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
  @Input()
  title = $localize`Email Document`

  @Input()
  documentId: number

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

  constructor(
    private activeModal: NgbActiveModal,
    private documentService: DocumentService,
    private toastService: ToastService
  ) {
    super()
    this.loading = false
  }

  public emailDocument() {
    this.loading = true
    this.documentService
      .emailDocument(
        this.documentId,
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
          this.toastService.showInfo($localize`Email sent`)
        },
        error: (e) => {
          this.loading = false
          this.toastService.showError($localize`Error emailing document`, e)
        },
      })
  }

  public close() {
    this.activeModal.close()
  }
}
