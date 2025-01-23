import { AsyncPipe } from '@angular/common'
import {
  AfterViewInit,
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
} from '@angular/core'
import { RouterModule } from '@angular/router'
import {
  NgbProgressbarModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import { delay, map } from 'rxjs/operators'
import {
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  Document,
} from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { IsNumberPipe } from 'src/app/pipes/is-number.pipe'
import { UsernamePipe } from 'src/app/pipes/username.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SettingsService } from 'src/app/services/settings.service'
import { CustomFieldDisplayComponent } from '../../common/custom-field-display/custom-field-display.component'
import { PreviewPopupComponent } from '../../common/preview-popup/preview-popup.component'
import { TagComponent } from '../../common/tag/tag.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-document-card-small',
  templateUrl: './document-card-small.component.html',
  styleUrls: ['./document-card-small.component.scss'],
  imports: [
    DocumentTitlePipe,
    IsNumberPipe,
    PreviewPopupComponent,
    TagComponent,
    CustomFieldDisplayComponent,
    AsyncPipe,
    UsernamePipe,
    IfPermissionsDirective,
    CustomDatePipe,
    RouterModule,
    NgbTooltipModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
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
    of(true)
      .pipe(delay(50))
      .subscribe(() => {
        this.show = true
      })
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
