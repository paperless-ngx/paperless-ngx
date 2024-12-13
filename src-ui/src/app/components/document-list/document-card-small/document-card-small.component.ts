import {
  AfterViewInit,
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core'
import { map } from 'rxjs/operators'
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
  selector: 'pngx-document-card-small',
  templateUrl: './document-card-small.component.html',
  styleUrls: ['./document-card-small.component.scss'],
})
export class DocumentCardSmallComponent
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

  @Output()
  toggleSelected = new EventEmitter()

  @Input()
  document: Document

  @Input()
  displayFields: string[] = DEFAULT_DISPLAY_FIELDS.map((f) => f.id)

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

  moreTags: number = null

  @ViewChild('popupPreview') popupPreview: PreviewPopupComponent

  ngAfterViewInit(): void {
    setInterval(() => {
      this.show = true
    }, 50)
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

  get privateName() {
    return $localize`Private`
  }

  getTagsLimited$() {
    const limit = this.document.notes.length > 0 ? 6 : 7
    return this.document.tags$?.pipe(
      map((tags) => {
        if (tags.length > limit) {
          this.moreTags = tags.length - (limit - 1)
          return tags.slice(0, limit - 1)
        } else {
          return tags
        }
      })
    )
  }

  mouseLeaveCard() {
    this.popupPreview?.close()
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }
}
