import { HttpClient } from '@angular/common/http'
import {
  Component,
  DOCUMENT,
  inject,
  Input,
  OnDestroy,
  signal,
  ViewChild,
} from '@angular/core'
import { NgbPopover, NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { Options } from '@popperjs/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { first, Subject, takeUntil } from 'rxjs'
import { Document } from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { SafeUrlPipe } from 'src/app/pipes/safeurl.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { PngxPdfViewerComponent } from '../pdf-viewer/pdf-viewer.component'
import { PdfRenderMode } from '../pdf-viewer/pdf-viewer.types'

@Component({
  selector: 'pngx-preview-popup',
  templateUrl: './preview-popup.component.html',
  styleUrls: ['./preview-popup.component.scss'],
  imports: [
    NgbPopoverModule,
    DocumentTitlePipe,
    PngxPdfViewerComponent,
    SafeUrlPipe,
    NgxBootstrapIconsModule,
  ],
})
export class PreviewPopupComponent implements OnDestroy {
  PdfRenderMode = PdfRenderMode
  private domDocument = inject<Document>(DOCUMENT)
  private settingsService = inject(SettingsService)
  public readonly documentService = inject(DocumentService)
  private http = inject(HttpClient)

  private _document: Document
  @Input()
  set document(document: Document) {
    this._document = document
    this.init()
  }

  get document(): Document {
    return this._document
  }

  @Input()
  link: string

  @Input()
  linkClasses: string = 'btn btn-sm btn-outline-secondary'

  @Input()
  linkTarget: string = '_blank'

  @Input()
  linkTitle: string = $localize`Open preview`

  unsubscribeNotifier: Subject<any> = new Subject()

  readonly error = signal(false)

  readonly requiresPassword = signal(false)

  readonly previewText = signal<string>(null)

  @ViewChild('popover') popover: NgbPopover

  readonly mouseOnPreview = signal(false)

  readonly popoverClass = signal('shadow popover-preview')

  readonly popperOptions = (options: Partial<Options>): Partial<Options> => ({
    ...options,
    strategy: 'fixed',
  })

  get renderAsObject(): boolean {
    return (this.isPdf && this.useNativePdfViewer) || !this.isPdf
  }

  get previewUrl() {
    return this.documentService.getPreviewUrl(this.document.id)
  }

  get previewLink(): string {
    if (this.usePdfFlipbookViewer) {
      return new URL(
        `documents/${this.document.id}/flipbook`,
        this.domDocumentBaseUri()
      ).toString()
    }
    return this.previewUrl
  }

  get previewLinkTarget(): string {
    return this.linkTarget
  }

  get useNativePdfViewer(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER)
  }

  get usePdfFlipbookViewer(): boolean {
    return (
      this.isPdf &&
      !this.useNativePdfViewer &&
      this.settingsService.get(SETTINGS_KEYS.PDF_FLIPBOOK_VIEWER)
    )
  }

  get isPdf(): boolean {
    return (
      this.document?.archived_file_name?.length > 0 ||
      this.document?.mime_type?.includes('pdf')
    )
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
  }

  init() {
    if (this.document.mime_type?.includes('text')) {
      this.http
        .get(this.previewUrl, { responseType: 'text' })
        .pipe(first(), takeUntil(this.unsubscribeNotifier))
        .subscribe({
          next: (res) => {
            this.previewText.set(res.toString())
          },
          error: (err) => {
            this.error.set(err)
          },
        })
    }
  }

  onError(event: any) {
    if (event.name == 'PasswordException') {
      this.requiresPassword.set(true)
    } else {
      this.error.set(true)
    }
  }

  mouseEnterPreview() {
    this.mouseOnPreview.set(true)
    if (!this.popover.isOpen()) {
      // we're going to open but hide to pre-load content during hover delay
      this.popover.open()
      this.popoverClass.set('shadow popover-preview pe-none opacity-0')
      setTimeout(() => {
        if (this.mouseOnPreview()) {
          // show popover
          this.popoverClass.set(
            this.popoverClass().replace('pe-none opacity-0', '')
          )
        } else {
          this.popover.close(true)
        }
      }, 600)
    }
  }

  mouseLeavePreview() {
    this.mouseOnPreview.set(false)
  }

  public close(immediate: boolean = false) {
    setTimeout(
      () => {
        if (!this.mouseOnPreview()) this.popover.close()
      },
      immediate ? 0 : 300
    )
  }

  private domDocumentBaseUri(): string {
    return (this.domDocument as Document & { baseURI: string }).baseURI
  }
}
