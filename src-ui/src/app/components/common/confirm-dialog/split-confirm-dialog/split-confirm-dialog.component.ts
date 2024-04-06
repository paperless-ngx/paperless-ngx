import { Component } from '@angular/core'
import { ConfirmDialogComponent } from '../confirm-dialog.component'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DocumentService } from 'src/app/services/rest/document.service'
import { PDFDocumentProxy } from '../../pdf-viewer/typings'

@Component({
  selector: 'pngx-split-confirm-dialog',
  templateUrl: './split-confirm-dialog.component.html',
  styleUrl: './split-confirm-dialog.component.scss',
})
export class SplitConfirmDialogComponent extends ConfirmDialogComponent {
  public get pagesString(): string {
    let pagesStr = ''

    let lastPage = 1
    for (let i = 1; i <= this.totalPages; i++) {
      if (this.pages.has(i) || i === this.totalPages) {
        if (lastPage === i) {
          pagesStr += `${i},`
          lastPage = Math.min(i + 1, this.totalPages)
        } else {
          pagesStr += `${lastPage}-${i},`
          lastPage = Math.min(i + 1, this.totalPages)
        }
      }
    }

    return pagesStr.replace(/,$/, '')
  }

  private pages: Set<number> = new Set()

  public documentID: number
  public page: number = 1
  public totalPages: number

  public get pdfSrc(): string {
    return this.documentService.getPreviewUrl(this.documentID)
  }

  constructor(
    activeModal: NgbActiveModal,
    private documentService: DocumentService
  ) {
    super(activeModal)
    this.confirmButtonEnabled = this.pages.size > 0
  }

  pdfPreviewLoaded(pdf: PDFDocumentProxy) {
    this.totalPages = pdf.numPages
  }

  addSplit() {
    if (this.page === this.totalPages) return
    this.pages.add(this.page)
    this.pages = new Set(Array.from(this.pages).sort())
    this.confirmButtonEnabled = this.pages.size > 0
  }

  removeSplit(i: number) {
    let page = Array.from(this.pages)[Math.min(i, this.pages.size - 1)]
    this.pages.delete(page)
    this.confirmButtonEnabled = this.pages.size > 0
  }
}
