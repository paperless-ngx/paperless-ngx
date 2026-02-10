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
} from 'pdfjs-dist/legacy/build/pdf.mjs'
import {
  EventBus,
  PDFFindController,
  PDFLinkService,
  PDFSinglePageViewer,
  PDFViewer,
} from 'pdfjs-dist/web/pdf_viewer.mjs'
import {
  PdfRenderMode,
  PdfSource,
  PdfZoomLevel,
  PdfZoomScale,
  PngxPdfDocumentProxy,
} from './pdf-viewer.types'

@Component({
  selector: 'pngx-pdf-viewer',
  templateUrl: './pdf-viewer.component.html',
  styleUrl: './pdf-viewer.component.scss',
})
export class PngxPdfViewerComponent
  implements AfterViewInit, OnChanges, OnDestroy
{
  @Input() src!: PdfSource
  @Input() page?: number
  @Output() pageChange = new EventEmitter<number>()
  @Input() rotation?: number
  @Input() renderMode: PdfRenderMode = PdfRenderMode.All
  @Input() selectable = true
  @Input() searchQuery = ''
  @Input() zoom: PdfZoomLevel = PdfZoomLevel.One
  @Input() zoomScale: PdfZoomScale = PdfZoomScale.PageWidth

  @Output() afterLoadComplete = new EventEmitter<PngxPdfDocumentProxy>()
  @Output() rendered = new EventEmitter<void>()
  @Output() loadError = new EventEmitter<unknown>()

  @ViewChild('container', { static: true })
  private readonly container!: ElementRef<HTMLDivElement>

  @ViewChild('viewer', { static: true })
  private readonly viewer!: ElementRef<HTMLDivElement>

  private hasLoaded = false
  private loadingTask?: PDFDocumentLoadingTask
  private resizeObserver?: ResizeObserver
  private pdf?: PDFDocumentProxy
  private pdfViewer?: PDFViewer | PDFSinglePageViewer
  private hasRenderedPage = false
  private lastFindQuery = ''
  private lastViewerPage?: number

  private readonly eventBus = new EventBus()
  private readonly linkService = new PDFLinkService({ eventBus: this.eventBus })
  private readonly findController = new PDFFindController({
    eventBus: this.eventBus,
    linkService: this.linkService,
    updateMatchesCountOnProgress: false,
  })

  private readonly onPageRendered = () => {
    this.hasRenderedPage = true
    this.dispatchFindIfReady()
    this.rendered.emit()
  }
  private readonly onPagesInit = () => this.applyViewerState()
  private readonly onPageChanging = (evt: { pageNumber: number }) => {
    // Avoid [(page)] two-way binding re-triggers navigation
    this.lastViewerPage = evt.pageNumber
    this.pageChange.emit(evt.pageNumber)
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['src']) {
      this.resetViewerState()
      if (this.src) {
        this.loadDocument()
      }
      return
    }

    if (changes['zoomScale']) {
      this.setupResizeObserver()
    }

    if (changes['selectable'] || changes['renderMode']) {
      this.initViewer()
    }

    if (
      changes['page'] ||
      changes['zoom'] ||
      changes['zoomScale'] ||
      changes['rotation']
    ) {
      this.applyViewerState()
    }

    if (changes['searchQuery']) {
      this.dispatchFindIfReady()
    }
  }

  ngAfterViewInit(): void {
    this.setupResizeObserver()
    this.initViewer()
    if (!this.hasLoaded) {
      this.loadDocument()
      return
    }
    if (this.pdf) {
      this.applyViewerState()
    }
  }

  ngOnDestroy(): void {
    this.eventBus.off('pagerendered', this.onPageRendered)
    this.eventBus.off('pagesinit', this.onPagesInit)
    this.eventBus.off('pagechanging', this.onPageChanging)
    this.resizeObserver?.disconnect()
    this.loadingTask?.destroy()
    this.pdfViewer?.cleanup()
    this.pdfViewer = undefined
  }

  private resetViewerState(): void {
    this.hasLoaded = false
    this.hasRenderedPage = false
    this.lastFindQuery = ''
    this.lastViewerPage = undefined
    this.loadingTask?.destroy()
    this.loadingTask = undefined
    this.pdf = undefined
    this.linkService.setDocument(null)
    if (this.pdfViewer) {
      this.pdfViewer.setDocument(null)
      this.pdfViewer.currentPageNumber = 1
    }
  }

  private async loadDocument(): Promise<void> {
    if (this.hasLoaded) {
      return
    }

    this.hasLoaded = true
    this.hasRenderedPage = false
    this.lastFindQuery = ''
    this.loadingTask?.destroy()

    GlobalWorkerOptions.workerSrc = '/assets/js/pdf.worker.min.mjs'
    this.loadingTask = getDocument(this.src)

    try {
      const pdf = await this.loadingTask.promise
      this.pdf = pdf
      this.linkService.setDocument(pdf)
      this.findController.onIsPageVisible = () => true
      this.pdfViewer?.setDocument(pdf)
      this.applyViewerState()
      this.afterLoadComplete.emit(pdf)
    } catch (err) {
      this.loadError.emit(err)
    }
  }

  private setupResizeObserver(): void {
    this.resizeObserver?.disconnect()
    this.resizeObserver = new ResizeObserver(() => {
      this.applyScale()
    })
    this.resizeObserver.observe(this.container.nativeElement)
  }

  private initViewer(): void {
    this.viewer.nativeElement.innerHTML = ''
    this.pdfViewer?.cleanup()
    this.hasRenderedPage = false
    this.lastFindQuery = ''

    const textLayerMode = this.selectable === false ? 0 : 1
    const options = {
      container: this.container.nativeElement,
      viewer: this.viewer.nativeElement,
      eventBus: this.eventBus,
      linkService: this.linkService,
      findController: this.findController,
      textLayerMode,
      removePageBorders: true,
    }

    this.pdfViewer =
      this.renderMode === PdfRenderMode.Single
        ? new PDFSinglePageViewer(options)
        : new PDFViewer(options)
    this.linkService.setViewer(this.pdfViewer)

    this.eventBus.off('pagerendered', this.onPageRendered)
    this.eventBus.off('pagesinit', this.onPagesInit)
    this.eventBus.off('pagechanging', this.onPageChanging)
    this.eventBus.on('pagerendered', this.onPageRendered)
    this.eventBus.on('pagesinit', this.onPagesInit)
    this.eventBus.on('pagechanging', this.onPageChanging)

    if (this.pdf) {
      this.pdfViewer.setDocument(this.pdf)
      this.applyViewerState()
    }
  }

  private applyViewerState(): void {
    if (!this.pdfViewer) {
      return
    }
    const hasPages = this.pdfViewer.pagesCount > 0
    if (typeof this.rotation === 'number' && hasPages) {
      this.pdfViewer.pagesRotation = this.rotation
    }
    if (
      typeof this.page === 'number' &&
      hasPages &&
      this.page !== this.lastViewerPage
    ) {
      const nextPage = Math.min(
        Math.max(Math.trunc(this.page), 1),
        this.pdfViewer.pagesCount
      )
      this.pdfViewer.currentPageNumber = nextPage
    }
    if (this.page === this.lastViewerPage) {
      this.lastViewerPage = undefined
    }
    if (hasPages) {
      this.applyScale()
    }
    this.dispatchFindIfReady()
  }

  private applyScale(): void {
    if (!this.pdfViewer) {
      return
    }
    if (this.pdfViewer.pagesCount === 0) {
      return
    }
    const zoomFactor = Number(this.zoom) || 1
    this.pdfViewer.currentScaleValue = this.zoomScale
    if (zoomFactor !== 1) {
      this.pdfViewer.currentScale = this.pdfViewer.currentScale * zoomFactor
    }
  }

  private dispatchFindIfReady(): void {
    if (!this.hasRenderedPage) {
      return
    }
    const query = this.searchQuery.trim()
    if (query === this.lastFindQuery) {
      return
    }
    this.lastFindQuery = query
    this.eventBus.dispatch('find', {
      query,
      caseSensitive: false,
      highlightAll: query.length > 0,
      phraseSearch: true,
    })
  }
}
