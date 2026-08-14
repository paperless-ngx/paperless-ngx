import {
  AfterViewInit,
  Component,
  DOCUMENT,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
  inject,
  signal,
} from '@angular/core'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { SettingsService } from 'src/app/services/settings.service'
import { PngxPdfDocumentProxy } from '../pdf-viewer/pdf-viewer.types'

type PdfFlipbookPageMode = 'auto' | 'single' | 'double'

type DFlipBook = {
  contentProvider?: { pageCount?: number }
  dispose?: () => void
  end?: () => void
  next?: () => void
  prev?: () => void
  resize?: () => void
  setPageMode?: (isSingle: boolean) => void
  start?: () => void
  target?: {
    _activePage?: number
    pageCount?: number
    pageMode?: number
    gotoPage?: (page: number) => void
  }
  ui?: {
    switchFullscreen?: () => void
    update?: () => void
  }
  zoom?: (delta: number) => void
}

type JQueryWindow = Window &
  typeof globalThis & {
    $?: any
    DFLIP?: any
    dFlipLocation?: string
    jQuery?: any
  }

@Component({
  selector: 'pngx-pdf-flipbook-viewer',
  templateUrl: './pdf-flipbook-viewer.component.html',
  styleUrl: './pdf-flipbook-viewer.component.scss',
  imports: [NgbDropdownModule, NgxBootstrapIconsModule],
})
export class PdfFlipbookViewerComponent
  implements AfterViewInit, OnChanges, OnDestroy
{
  private static flipbookAssetsPromise?: Promise<void>
  private static readonly flipbookStyleIds = ['pngx-flipbook-dflip-css']

  private readonly document = inject<Document>(DOCUMENT)
  private readonly settings = inject(SettingsService)

  @Input() src!: string
  @Input() sourceRevision = 0
  @Input() password?: string
  @Input() page = 1

  @Output() pageChange = new EventEmitter<number>()
  @Output() afterLoadComplete = new EventEmitter<PngxPdfDocumentProxy>()
  @Output() loadError = new EventEmitter<unknown>()

  @ViewChild('container', { static: true })
  private readonly container!: ElementRef<HTMLDivElement>

  readonly loading = signal(false)
  readonly error = signal(false)
  readonly pageCount = signal(1)
  readonly activePageNumber = signal(1)
  readonly ready = signal(false)

  private flipbook?: DFlipBook
  private initialized = false
  private currentPage = 1
  private resizeObserver?: ResizeObserver
  private renderGeneration = 0

  ngAfterViewInit(): void {
    this.initialized = true
    this.resizeObserver = new ResizeObserver(() => this.flipbook?.resize?.())
    this.resizeObserver.observe(this.container.nativeElement)
    this.load()
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (
      changes['page'] &&
      !changes['page'].firstChange &&
      this.page !== this.currentPage
    ) {
      this.goToPage(this.page || 1)
    }

    if (
      this.initialized &&
      (changes['src'] || changes['sourceRevision'] || changes['password'])
    ) {
      this.load()
    }
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect()
    this.destroyFlipbook()
  }

  async load(): Promise<void> {
    if (!this.initialized || !this.src) return

    const generation = ++this.renderGeneration
    this.loading.set(true)
    this.error.set(false)
    this.destroyFlipbook()

    try {
      await this.loadFlipbookAssets()
      if (generation !== this.renderGeneration) return

      const win = window as JQueryWindow
      const $ = win.jQuery ?? win.$
      if (!$?.fn?.flipBook) {
        throw new Error('Flipbook flipBook plugin did not initialize')
      }

      this.currentPage = this.clampedPage(this.page || 1)
      this.flipbook = $(this.container.nativeElement).flipBook(this.src, {
        allControls: '',
        backgroundColor: '#0f0f0f',
        controlsPosition: 'hide',
        docParameters: this.pdfDocumentParameters(),
        duration: this.flipbookTurnDuration(),
        enableDownload: true,
        height: '100%',
        openPage: this.currentPage,
        pageMode: this.flipbookPageMode(win),
        paddingBottom: this.showToolbar() ? 86 : 30,
        scrollWheel: true,
        singlePageMode: win.DFLIP?.SINGLE_PAGE_MODE?.AUTO ?? null,
        transparent: false,
        webgl: true,
        onFlip: (book: DFlipBook) => this.onFlip(book),
        onReady: (book: DFlipBook) => this.onReady(book),
      })

      window.setTimeout(() => this.flipbook?.resize?.(), 100)
    } catch (err) {
      if (generation !== this.renderGeneration) return
      this.error.set(true)
      this.loading.set(false)
      this.loadError.emit(err)
    }
  }

  private onReady(book: DFlipBook): void {
    this.loading.set(false)
    this.ready.set(true)
    this.currentPage = this.activePage(book)
    this.activePageNumber.set(this.currentPage)
    this.pageCount.set(book.contentProvider?.pageCount ?? 1)
    this.afterLoadComplete.emit({
      numPages: book.contentProvider?.pageCount ?? 1,
    } as PngxPdfDocumentProxy)
    this.pageChange.emit(this.currentPage)
  }

  private onFlip(book: DFlipBook): void {
    const page = this.activePage(book)
    if (page === this.currentPage) return
    this.currentPage = page
    this.activePageNumber.set(page)
    this.pageChange.emit(page)
  }

  goToPage(page: number): void {
    const targetPage = this.clampedPage(page)
    this.flipbook?.target?.gotoPage?.(targetPage)
    this.currentPage = targetPage
    this.activePageNumber.set(targetPage)
    this.flipbook?.ui?.update?.()
    this.flipbook?.resize?.()
  }

  nextPage(): void {
    this.flipbook?.next?.()
  }

  previousPage(): void {
    this.flipbook?.prev?.()
  }

  firstPage(): void {
    this.flipbook?.start?.()
  }

  lastPage(): void {
    this.flipbook?.end?.()
  }

  zoomIn(): void {
    this.flipbook?.zoom?.(1)
  }

  zoomOut(): void {
    this.flipbook?.zoom?.(-1)
  }

  toggleFullscreen(): void {
    this.flipbook?.ui?.switchFullscreen?.()
  }

  togglePageMode(): void {
    const win = window as JQueryWindow
    const singlePageMode = win.DFLIP?.PAGE_MODE?.SINGLE ?? 1
    this.flipbook?.setPageMode?.(
      this.flipbook.target?.pageMode !== singlePageMode
    )
  }

  download(): void {
    const link = this.document.createElement('a')
    link.href = this.src
    link.download = ''
    link.target = '_blank'
    this.document.body.appendChild(link)
    link.click()
    link.remove()
  }

  print(): void {
    const frame = this.document.createElement('iframe')
    frame.style.position = 'fixed'
    frame.style.right = '0'
    frame.style.bottom = '0'
    frame.style.width = '0'
    frame.style.height = '0'
    frame.style.border = '0'
    frame.onload = () => {
      frame.contentWindow?.focus()
      frame.contentWindow?.print()
    }
    frame.src = this.src
    this.document.body.appendChild(frame)
  }

  showToolbar(): boolean {
    return this.settings.get(SETTINGS_KEYS.PDF_FLIPBOOK_BOTTOM_PANEL)
  }

  private activePage(book: DFlipBook): number {
    return this.clampedPage(book.target?._activePage ?? this.currentPage)
  }

  private clampedPage(page: number): number {
    return Math.max(1, Math.trunc(page || 1))
  }

  private flipbookPageMode(win: JQueryWindow): number | null {
    const pageMode = this.settings.get(
      SETTINGS_KEYS.PDF_FLIPBOOK_PAGE_MODE
    ) as PdfFlipbookPageMode

    switch (pageMode) {
      case 'single':
        return win.DFLIP?.PAGE_MODE?.SINGLE ?? 1
      case 'double':
        return win.DFLIP?.PAGE_MODE?.DOUBLE ?? 2
      default:
        return win.DFLIP?.PAGE_MODE?.AUTO ?? null
    }
  }

  private flipbookTurnDuration(): number {
    const duration = this.settings.get(SETTINGS_KEYS.PDF_FLIPBOOK_TURN_DURATION)
    return [500, 800, 1200].includes(duration) ? duration : 800
  }

  private pdfDocumentParameters(): Record<string, unknown> {
    return {
      url: this.src,
      password: this.password,
      withCredentials: true,
      rangeChunkSize: 524288,
      cMapPacked: true,
      cMapUrl: this.assetUrl('flipbook/lib/js/libs/cmaps/'),
      imageResourcesPath: this.assetUrl('flipbook/lib/images/pdfjs/'),
      disableAutoFetch: true,
      disableStream: true,
    }
  }

  private destroyFlipbook(): void {
    this.flipbook?.dispose?.()
    this.flipbook = undefined
    this.ready.set(false)
    this.pageCount.set(1)
    this.activePageNumber.set(1)
    this.container?.nativeElement.replaceChildren()
  }

  private loadFlipbookAssets(): Promise<void> {
    this.ensureFlipbookStyles()

    if (!PdfFlipbookViewerComponent.flipbookAssetsPromise) {
      const win = window as JQueryWindow
      win.dFlipLocation = this.assetUrl('flipbook/lib/')
      PdfFlipbookViewerComponent.flipbookAssetsPromise = this.loadScripts([
        ['pngx-flipbook-jquery-js', 'flipbook/lib/js/libs/jquery.min.js'],
        ['pngx-flipbook-three-js', 'flipbook/lib/js/libs/three.min.js'],
        ['pngx-flipbook-pdf-js', 'flipbook/lib/js/libs/pdf.min.js'],
        ['pngx-flipbook-mockup-js', 'flipbook/lib/js/libs/mockup.min.js'],
        ['pngx-flipbook-dflip-js', 'flipbook/lib/js/dflip/index.js', 'module'],
      ])
    }

    return PdfFlipbookViewerComponent.flipbookAssetsPromise
  }

  private ensureFlipbookStyles(): void {
    const styles: Array<[string, string]> = [
      [
        PdfFlipbookViewerComponent.flipbookStyleIds[0],
        'flipbook/lib/css/min.css',
      ],
    ]

    styles.forEach(([id, href]) => {
      if (this.document.getElementById(id)) return
      const link = this.document.createElement('link')
      link.id = id
      link.rel = 'stylesheet'
      link.href = this.assetUrl(href)
      this.document.head.appendChild(link)
    })
  }

  private async loadScripts(
    scripts: Array<[string, string, 'module'?]>
  ): Promise<void> {
    for (const [id, path, type] of scripts) {
      await this.loadScript(id, this.assetUrl(path), type)
    }
  }

  private loadScript(id: string, src: string, type?: 'module'): Promise<void> {
    const existing = this.document.getElementById(
      id
    ) as HTMLScriptElement | null
    if (existing?.dataset['loaded'] === 'true') return Promise.resolve()

    return new Promise((resolve, reject) => {
      const script = existing ?? this.document.createElement('script')
      script.id = id
      script.src = src
      if (type) script.type = type
      script.onload = () => {
        script.dataset['loaded'] = 'true'
        resolve()
      }
      script.onerror = () => reject(new Error(`Failed to load ${src}`))
      if (!existing) this.document.body.appendChild(script)
    })
  }

  private assetUrl(path: string): string {
    return new URL(`assets/${path}`, this.documentBaseUri()).toString()
  }

  private documentBaseUri(): string {
    return (this.document as Document & { baseURI: string }).baseURI
  }
}
