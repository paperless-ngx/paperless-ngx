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

export type PngxPdfDocumentProxy = PDFDocumentProxy
export type PdfSource = string | { url: string; password?: string }

export enum PdfRenderMode {
  Single = 'single',
  All = 'all',
}

export enum PdfZoomScale {
  PageFit = 'page-fit',
  PageWidth = 'page-width',
}

export enum PdfZoomLevel {
  Quarter = '.25',
  Half = '.5',
  ThreeQuarters = '.75',
  One = '1',
  OneAndHalf = '1.5',
  Two = '2',
  Three = '3',
}

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
  @Input() searchQuery?: string
  @Input() zoom: PdfZoomLevel = PdfZoomLevel.One
  @Input() zoomScale: PdfZoomScale = PdfZoomScale.PageWidth

  @Output() afterLoadComplete = new EventEmitter<PngxPdfDocumentProxy>()
  @Output() rendered = new EventEmitter<void>()
  @Output() error = new EventEmitter<unknown>()

  @ViewChild('container', { static: true })
  private container?: ElementRef<HTMLDivElement>

  @ViewChild('viewer', { static: true })
  private viewer?: ElementRef<HTMLDivElement>

  private hasLoaded = false
  private loadingTask?: PDFDocumentLoadingTask
  private resizeObserver?: ResizeObserver
  private pdf?: PDFDocumentProxy
  private pdfViewer?: PDFViewer | PDFSinglePageViewer
  private hasRenderedPage = false
  private lastFindQuery = ''

  private eventBus = new EventBus()
  private linkService = new PDFLinkService({ eventBus: this.eventBus })
  private findController = new PDFFindController({
    eventBus: this.eventBus,
    linkService: this.linkService,
    updateMatchesCountOnProgress: false,
  })

  private onPageRendered = () => {
    this.hasRenderedPage = true
    this.dispatchFindIfReady()
    this.rendered.emit()
  }
  private onPagesInit = () => this.applyScale()
  private onPageChanging = (evt: { pageNumber: number }) => {
    this.pageChange.emit(evt.pageNumber)
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['src']) {
      this.hasLoaded = false
      this.loadDocument()
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

    if (changes['searchQuery'] && this.pdf) {
      this.dispatchFindIfReady()
    }
  }

  ngAfterViewInit(): void {
    this.setupResizeObserver()
    this.initViewer()
    if (this.src && !this.hasLoaded) {
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

  private async loadDocument(): Promise<void> {
    if (!this.src || this.hasLoaded) {
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
      this.error.emit(err)
    }
  }

  private setupResizeObserver(): void {
    const container = this.container?.nativeElement
    this.resizeObserver?.disconnect()
    if (!container || typeof ResizeObserver === 'undefined') {
      return
    }

    this.resizeObserver = new ResizeObserver(() => {
      this.applyScale()
    })
    this.resizeObserver.observe(container)
  }

  private initViewer(): void {
    const container = this.container?.nativeElement
    const viewer = this.viewer?.nativeElement
    if (!container || !viewer) {
      return
    }

    viewer.innerHTML = ''
    this.pdfViewer?.cleanup()
    this.hasRenderedPage = false
    this.lastFindQuery = ''

    const textLayerMode = this.selectable === false ? 0 : 1
    const options = {
      container,
      viewer,
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
    if (typeof this.page === 'number' && hasPages) {
      this.pdfViewer.currentPageNumber = this.page
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
    if (!this.pdf || !this.hasRenderedPage) {
      return
    }
    const query = this.searchQuery?.trim() ?? ''
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
