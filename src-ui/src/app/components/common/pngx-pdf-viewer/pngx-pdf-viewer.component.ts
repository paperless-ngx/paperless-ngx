import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
} from '@angular/core'
import {
  getDocument,
  GlobalWorkerOptions,
  PDFDocumentLoadingTask,
  PDFDocumentProxy,
  PDFPageProxy,
  RenderTask,
} from 'pdfjs-dist/legacy/build/pdf.mjs'

export type PngxPdfDocumentProxy = PDFDocumentProxy

@Component({
  selector: 'pngx-pdf-viewer',
  templateUrl: './pngx-pdf-viewer.component.html',
  styleUrl: './pngx-pdf-viewer.component.scss',
})
export class PngxPdfViewerComponent
  implements AfterViewInit, OnChanges, OnDestroy
{
  @Input() src: unknown
  @Input() page?: number
  @Output() pageChange = new EventEmitter<number>()
  @Input() rotation?: number
  @Input() originalSize?: boolean
  @Input() showBorders?: boolean
  @Input() showAll?: boolean
  @Input() renderText?: boolean
  @Input() zoom?: number | string
  @Input() zoomScale?: string

  @Output('after-load-complete') afterLoadComplete =
    new EventEmitter<PngxPdfDocumentProxy>()
  @Output('page-rendered') pageRendered = new EventEmitter<void>()
  @Output('text-layer-rendered') textLayerRendered = new EventEmitter<void>()
  @Output() error = new EventEmitter<unknown>()

  // Placeholder to mirror ng2-pdf-viewer API used by callers.
  eventBus = {
    dispatch: (_eventName: string, _payload?: unknown) => undefined,
  }

  @ViewChild('container', { static: true })
  private container?: ElementRef<HTMLDivElement>

  private hasLoaded = false
  private loadingTask?: PDFDocumentLoadingTask
  private renderTasks: RenderTask[] = []
  private renderToken = 0

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['src']) {
      this.hasLoaded = false
      this.loadDocument()
      return
    }

    if (changes['page'] || changes['zoom'] || changes['zoomScale']) {
      this.renderDocument()
    }
  }

  ngAfterViewInit(): void {
    if (this.src && !this.hasLoaded) {
      this.loadDocument()
      return
    }
    if (this.loadingTask) {
      this.renderDocument()
    }
  }

  ngOnDestroy(): void {
    this.cancelRender()
    this.loadingTask?.destroy()
  }

  private async loadDocument(): Promise<void> {
    if (!this.src || this.hasLoaded) {
      return
    }

    this.hasLoaded = true
    this.cancelRender()
    this.loadingTask?.destroy()

    GlobalWorkerOptions.workerSrc = '/assets/js/pdf.worker.min.mjs'
    this.loadingTask = getDocument(this.normalizeSrc())

    try {
      const pdf = await this.loadingTask.promise
      this.afterLoadComplete.emit(pdf)
      await this.renderDocument(pdf)
    } catch (err) {
      this.error.emit(err)
    }
  }

  private async renderDocument(pdfDocument?: PDFDocumentProxy): Promise<void> {
    const container = this.container?.nativeElement
    if (!container) {
      return
    }

    const pdf = pdfDocument ?? (await this.loadingTask?.promise)
    if (!pdf) {
      return
    }

    this.cancelRender()
    container.innerHTML = ''

    const renderToken = ++this.renderToken
    const pagesToRender = this.showAll === false ? [this.page ?? 1] : []
    if (pagesToRender.length === 0) {
      for (let i = 1; i <= pdf.numPages; i++) {
        pagesToRender.push(i)
      }
    }

    for (const pageNumber of pagesToRender) {
      if (renderToken !== this.renderToken) {
        return
      }

      const page = await pdf.getPage(this.clampPage(pageNumber, pdf))
      if (renderToken !== this.renderToken) {
        return
      }

      const { pageContainer, canvas } = this.createPageCanvas(container)
      const viewport = this.getViewport(page)
      canvas.width = viewport.width
      canvas.height = viewport.height

      const context = canvas.getContext('2d')
      if (!context) {
        continue
      }

      const renderTask = page.render({ canvasContext: context, viewport })
      this.renderTasks.push(renderTask)
      await renderTask.promise

      if (renderToken !== this.renderToken) {
        return
      }

      this.pageRendered.emit()
      this.textLayerRendered.emit()
      page.cleanup()
      pageContainer.dataset['pageNumber'] = String(pageNumber)
    }
  }

  private createPageCanvas(container: HTMLDivElement): {
    pageContainer: HTMLDivElement
    canvas: HTMLCanvasElement
  } {
    const pageContainer = document.createElement('div')
    pageContainer.className = 'page'

    const canvas = document.createElement('canvas')
    pageContainer.appendChild(canvas)
    container.appendChild(pageContainer)

    return { pageContainer, canvas }
  }

  private getViewport(page: PDFPageProxy) {
    const rotation = this.rotation ?? 0
    const baseViewport = page.getViewport({ scale: 1, rotation })
    let scale = this.parseZoom() ?? 1

    if (this.zoomScale === 'page-fit' || this.zoomScale === 'page-width') {
      const container = this.container?.nativeElement
      const availableWidth = container?.clientWidth || baseViewport.width
      const availableHeight = container?.clientHeight || baseViewport.height
      if (this.zoomScale === 'page-width') {
        scale = availableWidth / baseViewport.width
      } else {
        scale = Math.min(
          availableWidth / baseViewport.width,
          availableHeight / baseViewport.height
        )
      }
    }

    return page.getViewport({ scale, rotation })
  }

  private parseZoom(): number | undefined {
    if (typeof this.zoom === 'number') {
      return this.zoom
    }
    if (typeof this.zoom === 'string') {
      const parsed = Number(this.zoom)
      return Number.isFinite(parsed) ? parsed : undefined
    }
    return undefined
  }

  private normalizeSrc() {
    if (typeof this.src === 'string') {
      return { url: this.src }
    }
    return this.src
  }

  private clampPage(page: number, pdf: PDFDocumentProxy): number {
    if (page < 1) {
      return 1
    }
    if (page > pdf.numPages) {
      return pdf.numPages
    }
    return page
  }

  private cancelRender(): void {
    this.renderToken++
    for (const task of this.renderTasks) {
      try {
        task.cancel()
      } catch {
        // ignore
      }
    }
    this.renderTasks = []
  }
}
