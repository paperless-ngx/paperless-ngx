import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
} from '@angular/core'

export interface PngxPdfDocumentProxy {
  numPages: number
}

@Component({
  selector: 'pngx-pdf-viewer',
  templateUrl: './pngx-pdf-viewer.component.html',
  styleUrl: './pngx-pdf-viewer.component.scss',
})
export class PngxPdfViewerComponent implements OnChanges {
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

  private hasLoaded = false

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['src']) {
      this.hasLoaded = false
      this.simulateLoad()
    }
  }

  private simulateLoad(): void {
    if (!this.src || this.hasLoaded) {
      return
    }

    this.hasLoaded = true
    queueMicrotask(() => {
      this.afterLoadComplete.emit({ numPages: 1 })
      this.pageRendered.emit()
      this.textLayerRendered.emit()
    })
  }
}
