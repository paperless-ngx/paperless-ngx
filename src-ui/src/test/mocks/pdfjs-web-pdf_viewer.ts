type EventHandler = (event?: unknown) => void

export class EventBus {
  private listeners = new Map<string, Set<EventHandler>>()

  on(eventName: string, listener: EventHandler): void {
    if (!this.listeners.has(eventName)) {
      this.listeners.set(eventName, new Set())
    }
    this.listeners.get(eventName)!.add(listener)
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

  constructor(_options?: unknown) {}
}

export class PDFLinkService {
  setDocument(_document: unknown): void {}
  setViewer(_viewer: unknown): void {}
}

class BaseViewer {
  pagesCount = 0
  currentScale = 1
  currentScaleValue: string | number = 1
  pagesRotation = 0

  private eventBus?: EventBus
  private _currentPageNumber = 1

  constructor(options: { eventBus?: EventBus }) {
    this.eventBus = options.eventBus
  }

  setDocument(document: { numPages?: number } | null | undefined): void {
    this.pagesCount = document?.numPages ?? 1
    this.eventBus?.dispatch('pagesinit', {})
    this.eventBus?.dispatch('pagerendered', {
      pageNumber: this._currentPageNumber,
    })
  }

  cleanup(): void {}

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
