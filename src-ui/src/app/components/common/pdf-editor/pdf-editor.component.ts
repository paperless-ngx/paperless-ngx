import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { Component, inject } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component'
import { PngxPdfViewerComponent } from '../pdf-viewer/pdf-viewer.component'
import {
  PdfRenderMode,
  PngxPdfDocumentProxy,
} from '../pdf-viewer/pdf-viewer.types'
import { PdfEditorEditMode } from './pdf-editor-edit-mode'

interface PageOperation {
  page: number
  rotate: number
  splitAfter: boolean
  selected?: boolean
  loaded?: boolean
}

@Component({
  selector: 'pngx-pdf-editor',
  templateUrl: './pdf-editor.component.html',
  styleUrl: './pdf-editor.component.scss',
  imports: [
    DragDropModule,
    FormsModule,
    NgxBootstrapIconsModule,
    PngxPdfViewerComponent,
  ],
})
export class PDFEditorComponent extends ConfirmDialogComponent {
  PdfRenderMode = PdfRenderMode
  public PdfEditorEditMode = PdfEditorEditMode

  private documentService = inject(DocumentService)
  private readonly settingsService = inject(SettingsService)
  activeModal: NgbActiveModal = inject(NgbActiveModal)

  documentID: number
  pages: PageOperation[] = []
  totalPages = 0
  editMode: PdfEditorEditMode = this.settingsService.get(
    SETTINGS_KEYS.PDF_EDITOR_DEFAULT_EDIT_MODE
  )
  deleteOriginal: boolean = false
  includeMetadata: boolean = true

  get pdfSrc(): string {
    return this.documentService.getPreviewUrl(this.documentID)
  }

  pdfLoaded(pdf: PngxPdfDocumentProxy) {
    this.totalPages = pdf.numPages
    this.pages = Array.from({ length: this.totalPages }, (_, i) => ({
      page: i + 1,
      rotate: 0,
      splitAfter: false,
      selected: false,
      loaded: false,
    }))
  }

  toggleSelection(i: number) {
    this.pages[i].selected = !this.pages[i].selected
  }

  rotate(i: number, counterclockwise: boolean = false) {
    this.pages[i].rotate =
      (this.pages[i].rotate + (counterclockwise ? -90 : 90) + 360) % 360
  }

  rotateSelected(dir: number) {
    for (let p of this.pages) {
      if (p.selected) {
        p.rotate = (p.rotate + dir + 360) % 360
      }
    }
  }

  remove(i: number) {
    this.pages.splice(i, 1)
  }

  toggleSplit(i: number) {
    this.pages[i].splitAfter = !this.pages[i].splitAfter
    if (this.pages[i].splitAfter) {
      // force create mode
      this.editMode = PdfEditorEditMode.Create
    }
  }

  selectAll() {
    this.pages.forEach((p) => (p.selected = true))
  }

  deselectAll() {
    this.pages.forEach((p) => (p.selected = false))
  }

  deleteSelected() {
    this.pages = this.pages.filter((p) => !p.selected)
  }

  hasSelection(): boolean {
    return this.pages.some((p) => p.selected)
  }

  hasSplit(): boolean {
    return this.pages.some((p) => p.splitAfter)
  }

  drop(event: CdkDragDrop<PageOperation[]>) {
    moveItemInArray(this.pages, event.previousIndex, event.currentIndex)
  }

  getOperations() {
    return this.pages.map((p, idx) => ({
      page: p.page,
      rotate: p.rotate,
      doc: this.computeDocIndex(idx),
    }))
  }

  private computeDocIndex(index: number): number {
    let docIndex = 0
    for (let i = 0; i <= index; i++) {
      if (this.pages[i].splitAfter && i < index) docIndex++
    }
    return docIndex
  }
}
