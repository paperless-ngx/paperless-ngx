import { AsyncPipe, NgClass, NgStyle } from '@angular/common'
import {
  Component,
  inject,
  Input,
  OnDestroy,
  OnInit,
  QueryList,
  signal,
  ViewChildren,
} from '@angular/core'
import { Router, RouterModule } from '@angular/router'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, takeUntil } from 'rxjs'
import { CustomFieldDisplayComponent } from 'src/app/components/common/custom-field-display/custom-field-display.component'
import { PreviewPopupComponent } from 'src/app/components/common/preview-popup/preview-popup.component'
import { TagComponent } from 'src/app/components/common/tag/tag.component'
import { DocumentCardLargeComponent } from 'src/app/components/document-list/document-card-large/document-card-large.component'
import { DocumentCardSmallComponent } from 'src/app/components/document-list/document-card-small/document-card-small.component'
import { LoadingComponentWithPermissions } from 'src/app/components/loading-component/loading.component'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import {
  DEFAULT_DASHBOARD_DISPLAY_FIELDS,
  DEFAULT_DASHBOARD_VIEW_PAGE_SIZE,
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  DisplayMode,
  Document,
} from 'src/app/data/document'
import {
  FILTER_CORRESPONDENT,
  FILTER_DOCUMENT_TYPE,
  FILTER_FULLTEXT_MORELIKE,
  FILTER_HAS_TAGS_ALL,
  FILTER_OWNER_ANY,
  FILTER_STORAGE_PATH,
} from 'src/app/data/filter-rule-type'
import { SavedView } from 'src/app/data/saved-view'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { CorrespondentNamePipe } from 'src/app/pipes/correspondent-name.pipe'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { DocumentTypeNamePipe } from 'src/app/pipes/document-type-name.pipe'
import { StoragePathNamePipe } from 'src/app/pipes/storage-path-name.pipe'
import { UsernamePipe } from 'src/app/pipes/username.pipe'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { WebsocketStatusService } from 'src/app/services/websocket-status.service'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'

@Component({
  selector: 'pngx-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.scss'],
  imports: [
    CustomFieldDisplayComponent,
    DocumentCardSmallComponent,
    DocumentCardLargeComponent,
    PreviewPopupComponent,
    TagComponent,
    WidgetFrameComponent,
    IfPermissionsDirective,
    UsernamePipe,
    CorrespondentNamePipe,
    DocumentTypeNamePipe,
    StoragePathNamePipe,
    AsyncPipe,
    DocumentTitlePipe,
    CustomDatePipe,
    NgClass,
    NgStyle,
    RouterModule,
    NgxBootstrapIconsModule,
  ],
})
export class SavedViewWidgetComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  private documentService = inject(DocumentService)
  private router = inject(Router)
  private list = inject(DocumentListViewService)
  private websocketStatusService = inject(WebsocketStatusService)
  openDocumentsService = inject(OpenDocumentsService)
  documentListViewService = inject(DocumentListViewService)
  permissionsService = inject(PermissionsService)
  private settingsService = inject(SettingsService)
  private customFieldService = inject(CustomFieldsService)
  private savedViewService = inject(SavedViewService)

  public DisplayMode = DisplayMode
  public DisplayField = DisplayField
  public CustomFieldDataType = CustomFieldDataType

  private customFields: CustomField[] = []

  @Input()
  savedView: SavedView

  readonly documents = signal<Document[]>([])

  unsubscribeNotifier: Subject<any> = new Subject()

  @ViewChildren('popover') popovers: QueryList<NgbPopover>
  popover: NgbPopover

  mouseOnPreview = false
  popoverHidden = true

  readonly displayMode = signal<DisplayMode>(null)

  readonly displayFields = signal<DisplayField[]>(
    DEFAULT_DASHBOARD_DISPLAY_FIELDS
  )

  readonly count = signal<number>(null)

  placeholderRows: number[] = []

  ngOnInit(): void {
    this.placeholderRows = Array.from(
      {
        length: this.savedView?.page_size ?? DEFAULT_DASHBOARD_VIEW_PAGE_SIZE,
      },
      (_, index) => index
    )
    this.displayMode.set(this.savedView.display_mode ?? DisplayMode.TABLE)

    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.CustomField
      )
    ) {
      this.customFieldService
        .listAll()
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe((customFields) => {
          this.customFields = customFields.results
        })
    }

    if (
      this.savedView.display_fields &&
      this.savedView.display_fields.length > 0
    ) {
      this.displayFields = this.savedView.display_fields
    }

    // filter by perms etc
    this.displayFields = this.displayFields.filter(
      (field) =>
        this.settingsService.allDisplayFields().find((f) => f.id === field) !==
        undefined
    )

    this.reload()
    this.websocketStatusService
      .onDocumentConsumptionFinished()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.reload()
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  reload() {
    this.loading = this.documents.length == 0
    this.show = true
    this.documentService
      .listFiltered(
        1,
        this.savedView?.page_size ?? DEFAULT_DASHBOARD_VIEW_PAGE_SIZE,
        this.savedView.sort_field,
        this.savedView.sort_reverse,
        this.savedView.filter_rules,
        { truncate_content: true }
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.documents.set(result.results)
        this.count.set(result.count)
        this.savedViewService.setDocumentCount(this.savedView, result.count)
        this.loading = false
        this.show = true
      })
  }

  showAll() {
    if (this.savedView.show_in_sidebar) {
      this.router.navigate(['view', this.savedView.id])
    } else {
      this.router.navigate(['documents'], {
        queryParams: { view: this.savedView.id },
      })
    }
  }

  clickTag(tagID: number, event: MouseEvent = null) {
    event?.preventDefault()
    event?.stopImmediatePropagation()

    this.list.quickFilter([
      { rule_type: FILTER_HAS_TAGS_ALL, value: tagID.toString() },
    ])
  }

  clickCorrespondent(correspondentId: number, event: MouseEvent = null) {
    event?.preventDefault()
    event?.stopImmediatePropagation()

    this.list.quickFilter([
      { rule_type: FILTER_CORRESPONDENT, value: correspondentId.toString() },
    ])
  }

  clickDocType(docTypeId: number, event: MouseEvent = null) {
    event?.preventDefault()
    event?.stopImmediatePropagation()

    this.list.quickFilter([
      { rule_type: FILTER_DOCUMENT_TYPE, value: docTypeId.toString() },
    ])
  }

  clickStoragePath(storagePathId: number, event: MouseEvent = null) {
    event?.preventDefault()
    event?.stopImmediatePropagation()

    this.list.quickFilter([
      { rule_type: FILTER_STORAGE_PATH, value: storagePathId.toString() },
    ])
  }

  clickMoreLike(documentID: number) {
    this.list.quickFilter([
      { rule_type: FILTER_FULLTEXT_MORELIKE, value: documentID.toString() },
    ])
  }

  clickOwner(ownerID: number, event: MouseEvent = null) {
    event?.preventDefault()
    event?.stopImmediatePropagation()

    this.list.quickFilter([
      { rule_type: FILTER_OWNER_ANY, value: ownerID.toString() },
    ])
  }

  openDocumentDetail(document: Document) {
    this.router.navigate(['documents', document.id])
  }

  getDownloadUrl(document: Document): string {
    return this.documentService.getDownloadUrl(document.id)
  }

  public getColumnTitle(field: DisplayField): string {
    if (field.startsWith(DisplayField.CUSTOM_FIELD)) {
      const id = field.split('_')[2]
      return this.customFields.find((f) => f.id === parseInt(id))?.name
    }
    return DEFAULT_DISPLAY_FIELDS.find((f) => f.id === field)?.name
  }
}
