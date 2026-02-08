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
  TextLayer,
} from 'pdfjs-dist/legacy/build/pdf.mjs'

export type PngxPdfDocumentProxy = PDFDocumentProxy
@Component({
  selector: 'pngx-pdf-viewer',
  templateUrl: './pdf-viewer.component.html',
  styleUrl: './pdf-viewer.component.scss',
})
export class PngxPdfViewerComponent
  implements AfterViewInit, OnChanges, OnDestroy
{
  @Input() src: unknown
  @Input() page?: number
  @Output() pageChange = new EventEmitter<number>()
  @Input() rotation?: number
  @Input('original-size') originalSize?: boolean
  @Input('show-borders') showBorders?: boolean
  @Input('show-all') showAll?: boolean
  @Input('render-text') renderText?: boolean
  @Input() zoom?: number | string
  @Input('zoom-scale') zoomScale?: string

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
  private textLayers: TextLayer[] = []
  private renderToken = 0
  private resizeObserver?: ResizeObserver
  private lastObservedWidth = 0
  private lastObservedHeight = 0

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['src']) {
      this.hasLoaded = false
      this.loadDocument()
      return
    }

    if (changes['zoomScale']) {
      this.setupResizeObserver()
    }

    if (changes['page'] || changes['zoom'] || changes['zoomScale']) {
      this.renderDocument()
    }
  }

  ngAfterViewInit(): void {
    this.setupResizeObserver()
    if (this.src && !this.hasLoaded) {
      this.loadDocument()
      return
    }
    if (this.loadingTask) {
      this.renderDocument()
    }
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect()
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
    const source = await this.resolveDocumentSource()
    this.loadingTask = getDocument(source)

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
    if (
      (this.zoomScale === 'page-fit' || this.zoomScale === 'page-width') &&
      (!container.clientWidth ||
        (this.zoomScale === 'page-fit' && !container.clientHeight))
    ) {
      requestAnimationFrame(() => {
        if (renderToken === this.renderToken) {
          void this.renderDocument(pdf)
        }
      })
      return
    }
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

      const clampedPage = this.clampPage(pageNumber, pdf)
      if (clampedPage !== pageNumber) {
        this.pageChange.emit(clampedPage)
      }
      const page = await pdf.getPage(clampedPage)
      if (renderToken !== this.renderToken) {
        return
      }

      const { pageContainer, canvas } = this.createPageCanvas(container)
      const viewport = this.getViewport(page)
      pageContainer.style.width = `${viewport.width}px`
      pageContainer.style.height = `${viewport.height}px`
      canvas.width = viewport.width
      canvas.height = viewport.height
      canvas.style.width = `${viewport.width}px`
      canvas.style.height = `${viewport.height}px`

      const context = canvas.getContext('2d')
      if (!context) {
        continue
      }

      const renderTask = page.render({
        canvas,
        canvasContext: context,
        viewport,
      })
      this.renderTasks.push(renderTask)
      await renderTask.promise

      if (renderToken !== this.renderToken) {
        return
      }

      if (this.renderText !== false) {
        await this.renderTextLayer(page, pageContainer, viewport)
      }

      this.pageRendered.emit()
      this.textLayerRendered.emit()
      page.cleanup()
      pageContainer.dataset['pageNumber'] = String(clampedPage)
    }
  }

  private createPageCanvas(container: HTMLDivElement): {
    pageContainer: HTMLDivElement
    canvas: HTMLCanvasElement
  } {
    const pageContainer = document.createElement('div')
    pageContainer.className = 'page'
    if (this.showBorders) {
      pageContainer.classList.add('show-borders')
    }

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

  private async resolveDocumentSource() {
    const src = this.normalizeSrc()
    if (!src) {
      return src
    }
    if (src instanceof ArrayBuffer) {
      return { data: src }
    }
    if (ArrayBuffer.isView(src)) {
      return { data: src }
    }
    if (typeof src === 'object') {
      const candidate = src as {
        data?: unknown
        url?: string
        password?: string
      }
      if (candidate.data) {
        return candidate
      }
      if (candidate.url) {
        const response = await fetch(candidate.url, {
          credentials: 'same-origin',
        })
        const data = await response.arrayBuffer()
        return { data, password: candidate.password }
      }
    }
    return src
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
    for (const layer of this.textLayers) {
      try {
        layer.cancel()
      } catch {
        // ignore
      }
    }
    this.textLayers = []
  }

  private setupResizeObserver(): void {
    const container = this.container?.nativeElement
    this.resizeObserver?.disconnect()
    if (!container || typeof ResizeObserver === 'undefined') {
      return
    }

    if (!this.shouldObserveResize()) {
      return
    }

    this.resizeObserver = new ResizeObserver(() => {
      const width = container.clientWidth
      const height = container.clientHeight
      if (
        Math.abs(width - this.lastObservedWidth) < 1 &&
        Math.abs(height - this.lastObservedHeight) < 1
      ) {
        return
      }
      this.lastObservedWidth = width
      this.lastObservedHeight = height
      if (this.loadingTask) {
        this.renderDocument()
      }
    })
    this.resizeObserver.observe(container)
  }

  private shouldObserveResize(): boolean {
    return this.zoomScale === 'page-fit' || this.zoomScale === 'page-width'
  }

  private async renderTextLayer(
    page: PDFPageProxy,
    pageContainer: HTMLDivElement,
    viewport: ReturnType<PDFPageProxy['getViewport']>
  ): Promise<void> {
    const textLayerDiv = document.createElement('div')
    textLayerDiv.className = 'textLayer'
    textLayerDiv.style.width = `${viewport.width}px`
    textLayerDiv.style.height = `${viewport.height}px`
    pageContainer.appendChild(textLayerDiv)

    const textContent = await page.getTextContent()
    const textLayer = new TextLayer({
      textContentSource: textContent,
      container: textLayerDiv,
      viewport,
    })
    this.textLayers.push(textLayer)
    await textLayer.render()
  }
}
