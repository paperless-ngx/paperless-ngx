import { Component, TemplateRef, ViewChild } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { PDFDocumentProxy, PdfViewerComponent } from 'ng2-pdf-viewer'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-delete-pages-confirm-dialog',
  templateUrl: './delete-pages-confirm-dialog.component.html',
  styleUrl: './delete-pages-confirm-dialog.component.scss',
})
export class DeletePagesConfirmDialogComponent extends ConfirmDialogComponent {
  public documentID: number
  public pages: number[] = []
  public currentPage: number = 1
  public totalPages: number

  @ViewChild('pdfViewer') pdfViewer: PdfViewerComponent
  @ViewChild('pageCheckOverlay') pageCheckOverlay!: TemplateRef<any>
  private checks: HTMLElement[] = []

  public get pagesString(): string {
    return this.pages.join(', ')
  }

  public get pdfSrc(): string {
    return this.documentService.getPreviewUrl(this.documentID)
  }

  constructor(
    activeModal: NgbActiveModal,
    private documentService: DocumentService
  ) {
    super(activeModal)
  }

  public pdfPreviewLoaded(pdf: PDFDocumentProxy) {
    this.totalPages = pdf.numPages
  }

  pageRendered(event: CustomEvent) {
    const pageDiv = event.target as HTMLDivElement
    const check = this.pageCheckOverlay.createEmbeddedView({
      page: event.detail.pageNumber,
    })
    this.checks[event.detail.pageNumber - 1] = check.rootNodes[0]
    pageDiv?.insertBefore(check.rootNodes[0], pageDiv.firstChild)
    this.updateChecks()
  }

  pageCheckChanged(pageNumber: number) {
    if (!this.pages.includes(pageNumber)) this.pages.push(pageNumber)
    else if (this.pages.includes(pageNumber))
      this.pages.splice(this.pages.indexOf(pageNumber), 1)
    this.updateChecks()
  }

  private updateChecks() {
    this.checks.forEach((check, i) => {
      const input = check.getElementsByTagName('input')[0]
      input.checked = this.pages.includes(i + 1)
    })
  }
}
