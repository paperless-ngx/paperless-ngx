import { HttpClient } from '@angular/common/http'
import { Component, Input, OnDestroy, ViewChild } from '@angular/core'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import { first, Subject, takeUntil } from 'rxjs'
import { Document } from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'pngx-preview-popup',
  templateUrl: './preview-popup.component.html',
  styleUrls: ['./preview-popup.component.scss'],
})
export class PreviewPopupComponent implements OnDestroy {
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

  error = false

  requiresPassword: boolean = false

  previewText: string

  @ViewChild('popover') popover: NgbPopover

  mouseOnPreview: boolean = false

  popoverClass: string = 'shadow popover-preview'

  get renderAsObject(): boolean {
    return (this.isPdf && this.useNativePdfViewer) || !this.isPdf
  }

  get previewURL() {
    return this.documentService.getPreviewUrl(this.document.id)
  }

  get useNativePdfViewer(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.USE_NATIVE_PDF_VIEWER)
  }

  get isPdf(): boolean {
    return (
      this.document?.archived_file_name?.length > 0 ||
      this.document?.mime_type?.includes('pdf')
    )
  }

  constructor(
    private settingsService: SettingsService,
    private documentService: DocumentService,
    private http: HttpClient
  ) {}

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
  }

  init() {
    if (this.document.mime_type?.includes('text')) {
      this.http
        .get(this.previewURL, { responseType: 'text' })
        .pipe(first(), takeUntil(this.unsubscribeNotifier))
        .subscribe({
          next: (res) => {
            this.previewText = res.toString()
          },
          error: (err) => {
            this.error = err
          },
        })
    }
  }

  onError(event: any) {
    if (event.name == 'PasswordException') {
      this.requiresPassword = true
    } else {
      this.error = true
    }
  }

  get previewUrl() {
    return this.documentService.getPreviewUrl(this.document.id)
  }

  mouseEnterPreview() {
    this.mouseOnPreview = true
    if (!this.popover.isOpen()) {
      // we're going to open but hide to pre-load content during hover delay
      this.popover.open()
      this.popoverClass = 'shadow popover-preview pe-none opacity-0'
      setTimeout(() => {
        if (this.mouseOnPreview) {
          // show popover
          this.popoverClass = this.popoverClass.replace('pe-none opacity-0', '')
        } else {
          this.popover.close(true)
        }
      }, 600)
    }
  }

  mouseLeavePreview() {
    this.mouseOnPreview = false
  }

  public close(immediate: boolean = false) {
    setTimeout(
      () => {
        if (!this.mouseOnPreview) this.popover.close()
      },
      immediate ? 0 : 300
    )
  }
}
