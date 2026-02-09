type EventHandler = (event?: unknown) => void

export class EventBus {
  private readonly listeners = new Map<string, Set<EventHandler>>()

  on(eventName: string, listener: EventHandler): void {
    let listeners = this.listeners.get(eventName)
    if (!listeners) {
      listeners = new Set()
      this.listeners.set(eventName, listeners)
    }
    listeners.add(listener)
  }

  off(eventName: string, listener: EventHandler): void {
    this.listeners.get(eventName)?.delete(listener)
  }

  dispatch(eventName: string, event?: unknown): void {
    this.listeners.get(eventName)?.forEach((listener) => listener(event))
  }
}

export class PDFFindController {
  onIsPageVisible?: () => boolean
}

export class PDFLinkService {
  private document?: unknown
  private viewer?: unknown

  setDocument(document: unknown): void {
    this.document = document
  }

  setViewer(viewer: unknown): void {
    this.viewer = viewer
  }
}

class BaseViewer {
  pagesCount = 0
  currentScale = 1
  currentScaleValue: string | number = 1
  pagesRotation = 0
  readonly options: Record<string, unknown>

  private readonly eventBus?: EventBus
  private _currentPageNumber = 1

  constructor(options: { eventBus?: EventBus }) {
    this.options = options
    this.eventBus = options.eventBus
  }

  setDocument(document: { numPages?: number } | null | undefined): void {
    this.pagesCount = document?.numPages ?? 1
    this.eventBus?.dispatch('pagesinit', {})
    this.eventBus?.dispatch('pagerendered', {
      pageNumber: this._currentPageNumber,
    })
  }

  cleanup(): void {
    this.pagesCount = 0
  }

  get currentPageNumber(): number {
    return this._currentPageNumber
  }

  set currentPageNumber(value: number) {
    this._currentPageNumber = value
    this.eventBus?.dispatch('pagechanging', { pageNumber: value })
  }
}

export class PDFViewer extends BaseViewer {}
export class PDFSinglePageViewer extends BaseViewer {}
