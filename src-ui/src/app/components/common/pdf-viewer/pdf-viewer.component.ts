/**
 * This file is taken and modified from https://github.com/VadimDez/ng2-pdf-viewer/blob/10.0.0/src/app/pdf-viewer/pdf-viewer.component.ts
 * Created by vadimdez on 21/06/16.
 */
import {
  Component,
  Input,
  Output,
  ElementRef,
  EventEmitter,
  OnChanges,
  SimpleChanges,
  OnInit,
  OnDestroy,
  ViewChild,
  AfterViewChecked,
  NgZone,
} from '@angular/core'
import { from, fromEvent, Subject } from 'rxjs'
import { debounceTime, filter, takeUntil } from 'rxjs/operators'
import * as PDFJS from 'pdfjs-dist'
import * as PDFJSViewer from 'pdfjs-dist/web/pdf_viewer'

import { createEventBus } from './utils/event-bus-utils'

import type {
  PDFSource,
  PDFPageProxy,
  PDFProgressData,
  PDFDocumentProxy,
  PDFDocumentLoadingTask,
  PDFViewerOptions,
  ZoomScale,
} from './typings'
import { PDFSinglePageViewer } from 'pdfjs-dist/web/pdf_viewer'

PDFJS['verbosity'] = PDFJS.VerbosityLevel.ERRORS

export enum RenderTextMode {
  DISABLED,
  ENABLED,
  ENHANCED,
}

@Component({
  selector: 'pngx-pdf-viewer',
  templateUrl: './pdf-viewer.component.html',
  styleUrls: ['./pdf-viewer.component.scss'],
})
export class PdfViewerComponent
  implements OnChanges, OnInit, OnDestroy, AfterViewChecked
{
  static CSS_UNITS = 96.0 / 72.0
  static BORDER_WIDTH = 9

  @ViewChild('pdfViewerContainer')
  pdfViewerContainer!: ElementRef<HTMLDivElement>

  public eventBus!: PDFJSViewer.EventBus
  public pdfLinkService!: PDFJSViewer.PDFLinkService
  public pdfViewer!: PDFJSViewer.PDFViewer | PDFSinglePageViewer

  private isVisible = false

  private _cMapsUrl =
    typeof PDFJS !== 'undefined'
      ? `https://unpkg.com/pdfjs-dist@${(PDFJS as any).version}/cmaps/`
      : null
  private _imageResourcesPath =
    typeof PDFJS !== 'undefined'
      ? `https://unpkg.com/pdfjs-dist@${(PDFJS as any).version}/web/images/`
      : undefined
  private _renderText = true
  private _renderTextMode: RenderTextMode = RenderTextMode.ENABLED
  private _stickToPage = false
  private _originalSize = true
  private _pdf: PDFDocumentProxy | undefined
  private _page = 1
  private _zoom = 1
  private _zoomScale: ZoomScale = 'page-width'
  private _rotation = 0
  private _showAll = true
  private _canAutoResize = true
  private _fitToPage = false
  private _externalLinkTarget = 'blank'
  private _showBorders = false
  private lastLoaded!: string | Uint8Array | PDFSource | null
  private _latestScrolledPage!: number

  private resizeTimeout: number | null = null
  private pageScrollTimeout: number | null = null
  private isInitialized = false
  private loadingTask?: PDFDocumentLoadingTask | null
  private destroy$ = new Subject<void>()

  @Output('after-load-complete') afterLoadComplete =
    new EventEmitter<PDFDocumentProxy>()
  @Output('page-rendered') pageRendered = new EventEmitter<CustomEvent>()
  @Output('pages-initialized') pageInitialized = new EventEmitter<CustomEvent>()
  @Output('text-layer-rendered') textLayerRendered =
    new EventEmitter<CustomEvent>()
  @Output('error') onError = new EventEmitter<any>()
  @Output('on-progress') onProgress = new EventEmitter<PDFProgressData>()
  @Output() pageChange: EventEmitter<number> = new EventEmitter<number>(true)
  @Input() src?: string | Uint8Array | PDFSource

  @Input('c-maps-url')
  set cMapsUrl(cMapsUrl: string) {
    this._cMapsUrl = cMapsUrl
  }

  @Input('page')
  set page(_page: number | string | any) {
    _page = parseInt(_page, 10) || 1
    const originalPage = _page

    if (this._pdf) {
      _page = this.getValidPageNumber(_page)
    }

    this._page = _page
    if (originalPage !== _page) {
      this.pageChange.emit(_page)
    }
  }

  @Input('render-text')
  set renderText(renderText: boolean) {
    this._renderText = renderText
  }

  @Input('render-text-mode')
  set renderTextMode(renderTextMode: RenderTextMode) {
    this._renderTextMode = renderTextMode
  }

  @Input('original-size')
  set originalSize(originalSize: boolean) {
    this._originalSize = originalSize
  }

  @Input('show-all')
  set showAll(value: boolean) {
    this._showAll = value
  }

  @Input('stick-to-page')
  set stickToPage(value: boolean) {
    this._stickToPage = value
  }

  @Input('zoom')
  set zoom(value: number) {
    if (value <= 0) {
      return
    }

    this._zoom = value
  }

  get zoom() {
    return this._zoom
  }

  @Input('zoom-scale')
  set zoomScale(value: ZoomScale) {
    this._zoomScale = value
  }

  get zoomScale() {
    return this._zoomScale
  }

  @Input('rotation')
  set rotation(value: number) {
    if (!(typeof value === 'number' && value % 90 === 0)) {
      console.warn('Invalid pages rotation angle.')
      return
    }

    this._rotation = value
  }

  @Input('external-link-target')
  set externalLinkTarget(value: string) {
    this._externalLinkTarget = value
  }

  @Input('autoresize')
  set autoresize(value: boolean) {
    this._canAutoResize = Boolean(value)
  }

  @Input('fit-to-page')
  set fitToPage(value: boolean) {
    this._fitToPage = Boolean(value)
  }

  @Input('show-borders')
  set showBorders(value: boolean) {
    this._showBorders = Boolean(value)
  }

  static getLinkTarget(type: string) {
    switch (type) {
      case 'blank':
        return (PDFJSViewer as any).LinkTarget.BLANK
      case 'none':
        return (PDFJSViewer as any).LinkTarget.NONE
      case 'self':
        return (PDFJSViewer as any).LinkTarget.SELF
      case 'parent':
        return (PDFJSViewer as any).LinkTarget.PARENT
      case 'top':
        return (PDFJSViewer as any).LinkTarget.TOP
    }

    return null
  }

  constructor(
    private element: ElementRef<HTMLElement>,
    private ngZone: NgZone
  ) {
    PDFJS.GlobalWorkerOptions['workerSrc'] = 'assets/js/pdf.worker.min.js'
  }

  ngAfterViewChecked(): void {
    if (this.isInitialized) {
      return
    }

    const offset = this.pdfViewerContainer.nativeElement.offsetParent

    if (this.isVisible === true && offset == null) {
      this.isVisible = false
      return
    }

    if (this.isVisible === false && offset != null) {
      this.isVisible = true

      setTimeout(() => {
        this.initialize()
        this.ngOnChanges({ src: this.src } as any)
      })
    }
  }

  ngOnInit() {
    this.initialize()
    this.setupResizeListener()
  }

  ngOnDestroy() {
    this.clear()
    this.destroy$.next()
    this.loadingTask = null
  }

  ngOnChanges(changes: SimpleChanges) {
    if (!this.isVisible) {
      return
    }

    if ('src' in changes) {
      this.loadPDF()
    } else if (this._pdf) {
      if ('renderText' in changes || 'showAll' in changes) {
        this.setupViewer()
        this.resetPdfDocument()
      }
      if ('page' in changes) {
        const { page } = changes
        if (page.currentValue === this._latestScrolledPage) {
          return
        }

        // New form of page changing: The viewer will now jump to the specified page when it is changed.
        // This behavior is introduced by using the PDFSinglePageViewer
        this.pdfViewer.scrollPageIntoView({ pageNumber: this._page })
      }

      this.update()
    }
  }

  public updateSize() {
    from(
      this._pdf!.getPage(
        this.pdfViewer.currentPageNumber
      ) as unknown as Promise<PDFPageProxy>
    )
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (page: PDFPageProxy) => {
          const rotation = this._rotation + page.rotate
          const viewportWidth =
            (page as any).getViewport({
              scale: this._zoom,
              rotation,
            }).width * PdfViewerComponent.CSS_UNITS
          let scale = this._zoom
          let stickToPage = true

          // Scale the document when it shouldn't be in original size or doesn't fit into the viewport
          if (
            !this._originalSize ||
            (this._fitToPage &&
              viewportWidth > this.pdfViewerContainer.nativeElement.clientWidth)
          ) {
            const viewPort = (page as any).getViewport({ scale: 1, rotation })
            scale = this.getScale(viewPort.width, viewPort.height)
            stickToPage = !this._stickToPage
          }

          setTimeout(() => {
            this.pdfViewer.currentScale = scale
          })
        },
      })
  }

  public clear() {
    if (this.loadingTask && !this.loadingTask.destroyed) {
      this.loadingTask.destroy()
    }

    if (this._pdf) {
      this._latestScrolledPage = 0
      this._pdf.destroy()
      this._pdf = undefined
    }
  }

  private getPDFLinkServiceConfig() {
    const linkTarget = PdfViewerComponent.getLinkTarget(
      this._externalLinkTarget
    )

    if (linkTarget) {
      return { externalLinkTarget: linkTarget }
    }

    return {}
  }

  private initEventBus() {
    this.eventBus = createEventBus(PDFJSViewer, this.destroy$)

    fromEvent<CustomEvent>(this.eventBus, 'pagerendered')
      .pipe(takeUntil(this.destroy$))
      .subscribe((event) => {
        this.pageRendered.emit(event)
      })

    fromEvent<CustomEvent>(this.eventBus, 'pagesinit')
      .pipe(takeUntil(this.destroy$))
      .subscribe((event) => {
        this.pageInitialized.emit(event)
      })

    fromEvent(this.eventBus, 'pagechanging')
      .pipe(takeUntil(this.destroy$))
      .subscribe(({ pageNumber }: any) => {
        if (this.pageScrollTimeout) {
          clearTimeout(this.pageScrollTimeout)
        }

        this.pageScrollTimeout = window.setTimeout(() => {
          this._latestScrolledPage = pageNumber
          this.pageChange.emit(pageNumber)
        }, 100)
      })

    fromEvent<CustomEvent>(this.eventBus, 'textlayerrendered')
      .pipe(takeUntil(this.destroy$))
      .subscribe((event) => {
        this.textLayerRendered.emit(event)
      })
  }

  private initPDFServices() {
    this.pdfLinkService = new PDFJSViewer.PDFLinkService({
      eventBus: this.eventBus,
      ...this.getPDFLinkServiceConfig(),
    })
  }

  private getPDFOptions(): PDFViewerOptions {
    return {
      eventBus: this.eventBus,
      container: this.element.nativeElement.querySelector('div')!,
      removePageBorders: !this._showBorders,
      linkService: this.pdfLinkService,
      textLayerMode: this._renderText
        ? this._renderTextMode
        : RenderTextMode.DISABLED,
      imageResourcesPath: this._imageResourcesPath,
    }
  }

  private setupViewer() {
    PDFJS['disableTextLayer'] = !this._renderText

    this.initPDFServices()

    if (this._showAll) {
      this.pdfViewer = new PDFJSViewer.PDFViewer(this.getPDFOptions())
    } else {
      this.pdfViewer = new PDFJSViewer.PDFSinglePageViewer(this.getPDFOptions())
    }
    this.pdfLinkService.setViewer(this.pdfViewer)

    this.pdfViewer._currentPageNumber = this._page
  }

  private getValidPageNumber(page: number): number {
    if (page < 1) {
      return 1
    }

    if (page > this._pdf!.numPages) {
      return this._pdf!.numPages
    }

    return page
  }

  private getDocumentParams() {
    const srcType = typeof this.src

    if (!this._cMapsUrl) {
      return this.src
    }

    const params: any = {
      cMapUrl: this._cMapsUrl,
      cMapPacked: true,
      enableXfa: true,
    }

    if (srcType === 'string') {
      params.url = this.src
    } else if (srcType === 'object') {
      if ((this.src as any).byteLength !== undefined) {
        params.data = this.src
      } else {
        Object.assign(params, this.src)
      }
    }

    return params
  }

  private loadPDF() {
    if (!this.src) {
      return
    }

    if (this.lastLoaded === this.src) {
      this.update()
      return
    }

    this.clear()

    if (this.pdfViewer) {
      this.pdfViewer._resetView()
      this.pdfViewer = null
    }

    this.setupViewer()

    try {
      this.loadingTask = PDFJS.getDocument(this.getDocumentParams())

      this.loadingTask!.onProgress = (progressData: PDFProgressData) => {
        this.onProgress.emit(progressData)
      }

      const src = this.src

      from(this.loadingTask!.promise as Promise<PDFDocumentProxy>)
        .pipe(takeUntil(this.destroy$))
        .subscribe({
          next: (pdf) => {
            this._pdf = pdf
            this.lastLoaded = src

            this.afterLoadComplete.emit(pdf)
            this.resetPdfDocument()

            this.update()
          },
          error: (error) => {
            this.lastLoaded = null
            this.onError.emit(error)
          },
        })
    } catch (e) {
      this.onError.emit(e)
    }
  }

  private update() {
    this.page = this._page

    this.render()
  }

  private render() {
    this._page = this.getValidPageNumber(this._page)

    if (
      this._rotation !== 0 ||
      this.pdfViewer.pagesRotation !== this._rotation
    ) {
      setTimeout(() => {
        this.pdfViewer.pagesRotation = this._rotation
      })
    }

    if (this._stickToPage) {
      setTimeout(() => {
        this.pdfViewer.currentPageNumber = this._page
      })
    }

    this.updateSize()
  }

  private getScale(viewportWidth: number, viewportHeight: number) {
    const borderSize = this._showBorders
      ? 2 * PdfViewerComponent.BORDER_WIDTH
      : 0
    const pdfContainerWidth =
      this.pdfViewerContainer.nativeElement.clientWidth - borderSize
    const pdfContainerHeight =
      this.pdfViewerContainer.nativeElement.clientHeight - borderSize

    if (
      pdfContainerHeight === 0 ||
      viewportHeight === 0 ||
      pdfContainerWidth === 0 ||
      viewportWidth === 0
    ) {
      return 1
    }

    let ratio = 1
    switch (this._zoomScale) {
      case 'page-fit':
        ratio = Math.min(
          pdfContainerHeight / viewportHeight,
          pdfContainerWidth / viewportWidth
        )
        break
      case 'page-height':
        ratio = pdfContainerHeight / viewportHeight
        break
      case 'page-width':
      default:
        ratio = pdfContainerWidth / viewportWidth
        break
    }

    return (this._zoom * ratio) / PdfViewerComponent.CSS_UNITS
  }

  private resetPdfDocument() {
    this.pdfLinkService.setDocument(this._pdf, null)
    this.pdfViewer.setDocument(this._pdf!)
  }

  private initialize(): void {
    if (!this.isVisible) {
      return
    }

    this.isInitialized = true
    this.initEventBus()
    this.setupViewer()
  }

  private setupResizeListener(): void {
    this.ngZone.runOutsideAngular(() => {
      fromEvent(window, 'resize')
        .pipe(
          debounceTime(100),
          filter(() => this._canAutoResize && !!this._pdf),
          takeUntil(this.destroy$)
        )
        .subscribe(() => {
          this.updateSize()
        })
    })
  }
}
