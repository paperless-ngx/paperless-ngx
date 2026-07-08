import { AsyncPipe } from '@angular/common'
import {
  AfterViewInit,
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
  inject,
  signal,
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
export class DocumentCardSmallComponent
  extends LoadingComponentWithPermissions
  implements AfterViewInit
{
  private documentService = inject(DocumentService)
  settingsService = inject(SettingsService)
  private selectedSignal = signal(false)
  private documentSignal = signal<Document>(undefined)
  private displayFieldsSignal = signal<string[]>(
    DEFAULT_DISPLAY_FIELDS.map((f) => f.id)
  )

  DisplayField = DisplayField

  @Input()
  get selected(): boolean {
    return this.selectedSignal()
  }

  set selected(selected: boolean) {
    this.selectedSignal.set(selected)
  }

  @Output()
  toggleSelected = new EventEmitter()

  @Input()
  get document(): Document {
    return this.documentSignal()
  }

  set document(document: Document) {
    this.documentSignal.set(document)
  }

  @Input()
  get displayFields(): string[] {
    return this.displayFieldsSignal()
  }

  set displayFields(displayFields: string[]) {
    this.displayFieldsSignal.set(displayFields)
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

  get moreTags(): number {
    const limit = this.document?.notes.length > 0 ? 6 : 7
    return this.document?.tags.length > limit
      ? this.document.tags.length - (limit - 1)
      : null
  }

  @ViewChild('popupPreview') popupPreview: PreviewPopupComponent

  ngAfterViewInit(): void {
    this.show = true
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

  get tagIDs() {
    const limit = this.document.notes.length > 0 ? 6 : 7
    if (this.document.tags.length > limit) {
      return this.document.tags.slice(0, limit - 1)
    } else {
      return this.document.tags
    }
  }

  mouseLeaveCard() {
    this.popupPreview?.close()
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }
}
