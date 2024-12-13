import {
  AfterViewInit,
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core'
import {
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  Document,
} from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { PreviewPopupComponent } from '../../common/preview-popup/preview-popup.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-document-card-large',
  templateUrl: './document-card-large.component.html',
  styleUrls: ['./document-card-large.component.scss'],
})
export class DocumentCardLargeComponent
  extends LoadingComponentWithPermissions
  implements AfterViewInit
{
  DisplayField = DisplayField

  constructor(
    private documentService: DocumentService,
    public settingsService: SettingsService
  ) {
    super()
  }

  @Input()
  selected = false

  @Input()
  displayFields: string[] = DEFAULT_DISPLAY_FIELDS.map((f) => f.id)

  @Output()
  toggleSelected = new EventEmitter()

  get selectable() {
    return this.toggleSelected.observers.length > 0
  }

  @Input()
  document: Document

  @Output()
  dblClickDocument = new EventEmitter()

  @Output()
  clickTag = new EventEmitter<number>()

  @Output()
  clickCorrespondent = new EventEmitter<number>()

  @Output()
  clickDocumentType = new EventEmitter<number>()

  @Output()
  clickStoragePath = new EventEmitter<number>()

  @Output()
  clickMoreLike = new EventEmitter()

  @ViewChild('popupPreview') popupPreview: PreviewPopupComponent

  mouseOnPreview = false
  popoverHidden = true

  ngAfterViewInit(): void {
    setInterval(() => {
      this.show = true
    }, 100)
  }

  get searchScoreClass() {
    if (this.document.__search_hit__) {
      if (this.document.__search_hit__.score > 0.7) {
        return 'success'
      } else if (this.document.__search_hit__.score > 0.3) {
        return 'warning'
      } else {
        return 'danger'
      }
    }
  }

  get searchNoteHighlights() {
    let highlights = []
    if (
      this.document['__search_hit__'] &&
      this.document['__search_hit__'].note_highlights
    ) {
      // only show notes with a match
      highlights = (this.document['__search_hit__'].note_highlights as string)
        .split(',')
        .filter((highlight) => highlight.includes('<span'))
    }
    return highlights
  }

  getIsThumbInverted() {
    return this.settingsService.get(SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED)
  }

  getThumbUrl() {
    return this.documentService.getThumbUrl(this.document.id)
  }

  getDownloadUrl() {
    return this.documentService.getDownloadUrl(this.document.id)
  }

  mouseLeaveCard() {
    this.popupPreview?.close()
  }

  get contentTrimmed() {
    return (
      this.document.content.substring(0, 500) +
      (this.document.content.length > 500 ? '...' : '')
    )
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }
}
