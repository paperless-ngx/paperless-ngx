import { Component, OnInit, inject } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { PDFDocumentProxy, PdfViewerModule } from 'ng2-pdf-viewer'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Document } from 'src/app/data/document'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-split-confirm-dialog',
  templateUrl: './split-confirm-dialog.component.html',
  styleUrl: './split-confirm-dialog.component.scss',
  imports: [
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
    PdfViewerModule,
  ],
})
export class SplitConfirmDialogComponent
  extends ConfirmDialogComponent
  implements OnInit
{
  private documentService = inject(DocumentService)
  private permissionService = inject(PermissionsService)

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
  private document: Document
  public page: number = 1
  public totalPages: number
  public deleteOriginal: boolean = false

  public get canSplit(): boolean {
    return (
      this.page < this.totalPages &&
      this.pages.size < this.totalPages - 1 &&
      !this.pages.has(this.page)
    )
  }

  public get pdfSrc(): string {
    return this.documentService.getPreviewUrl(this.documentID)
  }

  constructor() {
    super()
    this.confirmButtonEnabled = this.pages.size > 0
  }

  ngOnInit(): void {
    this.documentService.get(this.documentID).subscribe((r) => {
      this.document = r
    })
  }

  pdfPreviewLoaded(pdf: PDFDocumentProxy) {
    this.totalPages = pdf.numPages
  }

  addSplit() {
    if (this.page === this.totalPages) return
    this.pages.add(this.page)
    this.pages = new Set(Array.from(this.pages).sort((a, b) => a - b))
    this.confirmButtonEnabled = this.pages.size > 0
  }

  removeSplit(i: number) {
    let page = Array.from(this.pages)[Math.min(i, this.pages.size - 1)]
    this.pages.delete(page)
    this.confirmButtonEnabled = this.pages.size > 0
  }

  get userOwnsDocument(): boolean {
    return this.permissionService.currentUserOwnsObject(this.document)
  }
}
