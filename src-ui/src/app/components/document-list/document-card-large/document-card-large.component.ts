import { AsyncPipe } from '@angular/common'
import {
  AfterViewInit,
  Component,
  EventEmitter,
  Output,
  ViewChild,
  inject,
  input,
} from '@angular/core'
import { RouterModule } from '@angular/router'
import {
  NgbProgressbarModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  Document,
} from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CorrespondentNamePipe } from 'src/app/pipes/correspondent-name.pipe'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { DocumentTypeNamePipe } from 'src/app/pipes/document-type-name.pipe'
import { IsNumberPipe } from 'src/app/pipes/is-number.pipe'
import { StoragePathNamePipe } from 'src/app/pipes/storage-path-name.pipe'
import { UsernamePipe } from 'src/app/pipes/username.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CustomFieldDisplayComponent } from '../../common/custom-field-display/custom-field-display.component'
import { PreviewPopupComponent } from '../../common/preview-popup/preview-popup.component'
import { TagComponent } from '../../common/tag/tag.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-document-card-large',
  templateUrl: './document-card-large.component.html',
  styleUrls: ['./document-card-large.component.scss'],
  imports: [
    DocumentTitlePipe,
    IsNumberPipe,
    PreviewPopupComponent,
    TagComponent,
    CustomFieldDisplayComponent,
    AsyncPipe,
    UsernamePipe,
    CorrespondentNamePipe,
    DocumentTypeNamePipe,
    StoragePathNamePipe,
    IfPermissionsDirective,
    CustomDatePipe,
    RouterModule,
    NgbTooltipModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
})
export class DocumentCardLargeComponent
  extends LoadingComponentWithPermissions
  implements AfterViewInit
{
  private documentService = inject(DocumentService)
  settingsService = inject(SettingsService)
  readonly selected = input(false)
  readonly displayFields = input<string[]>(
    DEFAULT_DISPLAY_FIELDS.map((f) => f.id)
  )
  readonly document = input<Document>(undefined)

  DisplayField = DisplayField

  @Output()
  toggleSelected = new EventEmitter()

  get selectable() {
    return this.toggleSelected.observers.length > 0
  }

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
    this.show.set(true)
  }

  get searchScoreClass() {
    const document = this.document()
    if (document.__search_hit__) {
      if (document.__search_hit__.score > 0.7) {
        return 'success'
      } else if (document.__search_hit__.score > 0.3) {
        return 'warning'
      } else {
        return 'danger'
      }
    }
  }

  get searchNoteHighlights() {
    let highlights = []
    const document = this.document()
    if (
      document['__search_hit__'] &&
      document['__search_hit__'].note_highlights
    ) {
      // only show notes with a match
      highlights = (document['__search_hit__'].note_highlights as string)
        .split(',')
        .filter((highlight) => highlight.includes('<span'))
    }
    return highlights
  }

  getIsThumbInverted() {
    return this.settingsService.get(SETTINGS_KEYS.DARK_MODE_THUMB_INVERTED)
  }

  getThumbUrl() {
    return this.documentService.getThumbUrl(this.document().id)
  }

  getDownloadUrl() {
    return this.documentService.getDownloadUrl(this.document().id)
  }

  mouseLeaveCard() {
    this.popupPreview?.close()
  }

  get contentTrimmed() {
    const document = this.document()
    return (
      document.content.substring(0, 500) +
      (document.content.length > 500 ? '...' : '')
    )
  }

  get hasSearchHighlights() {
    return Boolean(this.document()?.__search_hit__?.highlights?.trim()?.length)
  }

  get shouldShowContentFallback() {
    const document = this.document()
    return (
      document?.__search_hit__?.score == null ||
      (!this.hasSearchHighlights && this.searchNoteHighlights.length === 0)
    )
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }
}
