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
import { Document } from 'src/app/data/document'
import {
  DocumentDisplayField,
  DashboardViewMode,
  SavedView,
  DOCUMENT_DISPLAY_FIELDS,
} from 'src/app/data/saved-view'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import {
  FILTER_CORRESPONDENT,
  FILTER_DOCUMENT_TYPE,
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
import { Results } from 'src/app/data/results'

@Component({
  selector: 'pngx-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.scss'],
})
export class SavedViewWidgetComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  public DashboardViewMode = DashboardViewMode
  public DashboardViewTableColumn = DocumentDisplayField
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

  visibleColumns: DocumentDisplayField[] = [
    DocumentDisplayField.TITLE,
    DocumentDisplayField.CREATED,
    DocumentDisplayField.ADDED,
  ]

  docLinkDocuments: Document[] = []

  ngOnInit(): void {
    this.reload()
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
          this.maybeGetDocuments()
        })
    }

    this.savedView.document_display_fields?.forEach((column) => {
      let type: PermissionType = Object.values(PermissionType).find((t) =>
        t.includes(column)
      )
      if (column.startsWith(DocumentDisplayField.CUSTOM_FIELD)) {
        type = PermissionType.CustomField
      }
      if (
        type &&
        this.permissionsService.currentUserCan(PermissionAction.View, type)
      )
        this.visibleColumns.push(column)
    })
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
        this.savedView.dashboard_view_limit,
        this.savedView.sort_field,
        this.savedView.sort_reverse,
        this.savedView.filter_rules,
        { truncate_content: true }
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.loading = false
        this.documents = result.results
        this.maybeGetDocuments()
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

  public getColumnTitle(column: DocumentDisplayField): string {
    if (column.startsWith(DocumentDisplayField.CUSTOM_FIELD)) {
      const id = column.split('_')[2]
      return this.customFields.find((c) => c.id === parseInt(id))?.name
    }
    return DOCUMENT_DISPLAY_FIELDS.find((c) => c.id === column)?.name
  }

  public getCustomFieldDataType(column_id: string): string {
    const customFieldId = parseInt(column_id.split('_')[2])
    return this.customFields.find((cf) => cf.id === customFieldId)?.data_type
  }

  public getCustomFieldValue(document: Document, column_id: string): any {
    const customFieldId = parseInt(column_id.split('_')[2])
    return document.custom_fields.find((cf) => cf.field === customFieldId)
      ?.value
  }

  public getMonetaryCustomFieldValue(
    document: Document,
    column_id: string
  ): Array<number | string> {
    const value = this.getCustomFieldValue(document, column_id)
    if (!value) return [null, null]
    const currencyCode = value.match(/[A-Z]{3}/)?.[0]
    const amount = parseFloat(value.replace(currencyCode, ''))
    return [amount, currencyCode]
  }

  maybeGetDocuments() {
    // retrieve documents for document link columns
    if (this.docLinkDocuments.length) return
    let docIds = []
    let docLinkColumns = []
    this.savedView.document_display_fields
      ?.filter((column) => column.startsWith(DocumentDisplayField.CUSTOM_FIELD))
      .forEach((column) => {
        if (
          this.getCustomFieldDataType(column) ===
          CustomFieldDataType.DocumentLink
        ) {
          docLinkColumns.push(column)
        }
      })
    this.documents.forEach((doc) => {
      docLinkColumns.forEach((column) => {
        const docs: number[] = this.getCustomFieldValue(doc, column)
        if (docs) {
          docIds = docIds.concat(docs)
        }
      })
    })

    if (docIds.length) {
      this.documentService
        .listAll(null, false, { id__in: docIds.join(',') })
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe((result: Results<Document>) => {
          this.docLinkDocuments = result.results
        })
    }
  }

  public getDocumentTitle(documentId: number): string {
    return this.docLinkDocuments.find((doc) => doc.id === documentId)?.title
  }
}
