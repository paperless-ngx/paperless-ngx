import { AsyncPipe, NgOptimizedImage } from '@angular/common'
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
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import {
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  Document,
} from 'src/app/data/document'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { CollapseTagsPipe } from 'src/app/pipes/collapse-tags.pipe'
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
    CollapseTagsPipe,
    NgOptimizedImage,
    UsernamePipe,
    CorrespondentNamePipe,
    DocumentTypeNamePipe,
    StoragePathNamePipe,
    CustomDatePipe,
    RouterModule,
    NgbTooltipModule,
    NgbProgressbarModule,
    BootstrapIconComponent,
  ],
})
export class DocumentCardSmallComponent
  extends LoadingComponentWithPermissions
  implements AfterViewInit
{
  private documentService = inject(DocumentService)
  settingsService = inject(SettingsService)
  readonly selected = input(false)
  readonly priority = input(false)
  readonly document = input<Document>(undefined)
  readonly displayFields = input<string[]>(
    DEFAULT_DISPLAY_FIELDS.map((f) => f.id)
  )

  DisplayField = DisplayField

  @Output()
  toggleSelected = new EventEmitter()

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

  private get tagLimit(): number {
    return this.document()?.notes.length > 0 ? 6 : 7
  }

  getMoreTags(tagIDs: number[]): number {
    const limit = this.tagLimit
    return tagIDs?.length > limit ? tagIDs.length - (limit - 1) : null
  }

  @ViewChild('popupPreview') popupPreview: PreviewPopupComponent

  ngAfterViewInit(): void {
    this.show.set(true)
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

  getTagIDs(tagIDs: number[]): number[] {
    const limit = this.tagLimit
    return tagIDs?.length > limit ? tagIDs.slice(0, limit - 1) : tagIDs
  }

  mouseLeaveCard() {
    this.popupPreview?.close()
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }
}
