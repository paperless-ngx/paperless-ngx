import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core'
import { ActivatedRoute } from '@angular/router'
import { Subject, first, takeUntil } from 'rxjs'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { PdfFlipbookViewerComponent } from '../common/pdf-flipbook-viewer/pdf-flipbook-viewer.component'
import { PngxPdfDocumentProxy } from '../common/pdf-viewer/pdf-viewer.types'

@Component({
  selector: 'pngx-document-flipbook',
  templateUrl: './document-flipbook.component.html',
  styleUrl: './document-flipbook.component.scss',
  imports: [PdfFlipbookViewerComponent],
})
export class DocumentFlipbookComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute)
  private documentService = inject(DocumentService)
  private documentTitlePipe = inject(DocumentTitlePipe)
  private unsubscribeNotifier = new Subject<void>()

  readonly documentId = signal<number>(undefined)
  readonly title = signal<string>('')
  readonly previewUrl = signal<string>(undefined)
  readonly currentPage = signal(1)
  readonly numPages = signal<number>(undefined)
  readonly requiresPassword = signal(false)
  readonly pdfPassword = signal<string>(undefined)
  readonly error = signal(false)

  ngOnInit(): void {
    this.route.paramMap
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((paramMap) => {
        const documentId = +paramMap.get('id')
        this.documentId.set(documentId)
        this.previewUrl.set(this.documentService.getPreviewUrl(documentId))
        this.currentPage.set(1)
        this.error.set(false)
        this.requiresPassword.set(false)
        this.pdfPassword.set(undefined)
        this.loadTitle(documentId)
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  onLoaded(pdf: PngxPdfDocumentProxy): void {
    this.numPages.set(pdf.numPages)
    this.requiresPassword.set(false)
  }

  onError(event: any): void {
    if (event.name === 'PasswordException') {
      this.requiresPassword.set(true)
      return
    }
    this.error.set(true)
  }

  onPasswordKeyUp(event: KeyboardEvent): void {
    if (event.key !== 'Enter') return
    this.pdfPassword.set((event.target as HTMLInputElement).value)
  }

  private loadTitle(documentId: number): void {
    this.documentService
      .get(documentId, null, 'id,title')
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (document) =>
          this.title.set(this.documentTitlePipe.transform(document.title)),
        error: () => this.title.set($localize`Preview`),
      })
  }
}
