import {
  Component,
  Input,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChildren,
} from '@angular/core'
import { Router } from '@angular/router'
import { Subject, takeUntil } from 'rxjs'
import {
  DEFAULT_DASHBOARD_DISPLAY_FIELDS,
  DEFAULT_DASHBOARD_VIEW_PAGE_SIZE,
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  DisplayMode,
  Document,
} from 'src/app/data/document'
import { SavedView } from 'src/app/data/saved-view'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import {
  FILTER_CORRESPONDENT,
  FILTER_DOCUMENT_TYPE,
  FILTER_FULLTEXT_MORELIKE,
  FILTER_HAS_TAGS_ALL,
  FILTER_STORAGE_PATH,
} from 'src/app/data/filter-rule-type'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { SettingsService } from 'src/app/services/settings.service'

@Component({
  selector: 'pngx-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.scss'],
})
export class SavedViewWidgetComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  public DisplayMode = DisplayMode
  public DisplayField = DisplayField
  public CustomFieldDataType = CustomFieldDataType

  loading: boolean = true

  private customFields: CustomField[] = []

  constructor(
    private documentService: DocumentService,
    private router: Router,
    private list: DocumentListViewService,
    private consumerStatusService: ConsumerStatusService,
    public openDocumentsService: OpenDocumentsService,
    public documentListViewService: DocumentListViewService,
    public permissionsService: PermissionsService,
    private settingsService: SettingsService,
    private customFieldService: CustomFieldsService
  ) {
    super()
  }

  @Input()
  savedView: SavedView

  documents: Document[] = []

  unsubscribeNotifier: Subject<any> = new Subject()

  @ViewChildren('popover') popovers: QueryList<NgbPopover>
  popover: NgbPopover

  mouseOnPreview = false
  popoverHidden = true

  displayMode: DisplayMode

  displayFields: DisplayField[] = DEFAULT_DASHBOARD_DISPLAY_FIELDS

  ngOnInit(): void {
    this.reload()
    this.displayMode = this.savedView.display_mode ?? DisplayMode.TABLE
    this.consumerStatusService
      .onDocumentConsumptionFinished()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.reload()
      })

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

    if (this.savedView.display_fields) {
      this.displayFields = this.savedView.display_fields
    }

    // filter by perms etc
    this.displayFields = this.displayFields.filter(
      (field) =>
        this.settingsService.allDisplayFields.find((f) => f.id === field) !==
        undefined
    )
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  reload() {
    this.loading = this.documents.length == 0
    this.documentService
      .listFiltered(
        1,
        this.savedView.page_size ?? DEFAULT_DASHBOARD_VIEW_PAGE_SIZE,
        this.savedView.sort_field,
        this.savedView.sort_reverse,
        this.savedView.filter_rules,
        { truncate_content: true }
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.loading = false
        this.documents = result.results
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

  openDocumentDetail(document: Document) {
    this.router.navigate(['documents', document.id])
  }

  getPreviewUrl(document: Document): string {
    return this.documentService.getPreviewUrl(document.id)
  }

  getDownloadUrl(document: Document): string {
    return this.documentService.getDownloadUrl(document.id)
  }

  mouseEnterPreviewButton(doc: Document) {
    const newPopover = this.popovers.get(this.documents.indexOf(doc))
    if (this.popover !== newPopover && this.popover?.isOpen())
      this.popover.close()
    this.popover = newPopover
    this.mouseOnPreview = true
    if (!this.popover.isOpen()) {
      // we're going to open but hide to pre-load content during hover delay
      this.popover.open()
      this.popoverHidden = true
      setTimeout(() => {
        if (this.mouseOnPreview) {
          // show popover
          this.popoverHidden = false
        } else {
          this.popover.close()
        }
      }, 600)
    }
  }

  mouseEnterPreview() {
    this.mouseOnPreview = true
  }

  mouseLeavePreview() {
    this.mouseOnPreview = false
    this.maybeClosePopover()
  }

  mouseLeavePreviewButton() {
    this.mouseOnPreview = false
    this.maybeClosePopover()
  }

  maybeClosePopover() {
    setTimeout(() => {
      if (!this.mouseOnPreview) this.popover?.close()
    }, 300)
  }

  public getColumnTitle(field: DisplayField): string {
    if (field.startsWith(DisplayField.CUSTOM_FIELD)) {
      const id = field.split('_')[2]
      return this.customFields.find((f) => f.id === parseInt(id))?.name
    }
    return DEFAULT_DISPLAY_FIELDS.find((f) => f.id === field)?.name
  }
}
