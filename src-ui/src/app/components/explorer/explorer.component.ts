import {
  Component,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core'
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import {
  Subject,
  filter,
  first,
  map,
  switchMap,
  take,
  takeUntil,
  tap,
} from 'rxjs'
import {
  FilterRule,
  filterRulesDiffer,
  isFullTextFilterRule,
} from 'src/app/data/filter-rule'
import { FILTER_FULLTEXT_MORELIKE } from 'src/app/data/filter-rule-type'
import { PaperlessDocument } from 'src/app/data/paperless-document'
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view'
import { SETTINGS_KEYS } from 'src/app/data/paperless-uisettings'
import {
  SortEvent,
  SortableDirective,
} from 'src/app/directives/sortable.directive'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import {
  DOCUMENT_SORT_FIELDS,
  DOCUMENT_SORT_FIELDS_FULLTEXT,
} from 'src/app/services/rest/document.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { StoragePathListViewService } from 'src/app/services/storage-path-list-view.service'
import { ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { FilterEditorComponent } from './filter-editor/filter-editor.component'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'

@Component({
  selector: 'app-explorer',
  templateUrl: './explorer.component.html',
  styleUrls: ['./explorer.component.scss'],
})
export class ExplorerComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  constructor(
    public list: StoragePathListViewService,
    public savedViewService: SavedViewService,
    public route: ActivatedRoute,
    private router: Router,
    private toastService: ToastService,
    private modalService: NgbModal,
    private consumerStatusService: ConsumerStatusService,
    public openDocumentsService: OpenDocumentsService,
    private settingsService: SettingsService
  ) {
    super()
  }

  @ViewChild('filterEditor')
  private filterEditor: FilterEditorComponent

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>

  displayMode = 'smallCards' // largeCards, smallCards, details

  unmodifiedFilterRules: FilterRule[] = []
  private unmodifiedSavedView: PaperlessSavedView

  private unsubscribeNotifier: Subject<any> = new Subject()

  get folderPath(): string {
    return this.list.currentFolderPath
  }

  get savedViewIsModified(): boolean {
    if (!this.list.activeSavedViewId || !this.unmodifiedSavedView) return false
    else {
      return (
        this.unmodifiedSavedView.sort_field !== this.list.sortField ||
        this.unmodifiedSavedView.sort_reverse !== this.list.sortReverse ||
        filterRulesDiffer(
          this.unmodifiedSavedView.filter_rules,
          this.list.filterRules
        )
      )
    }
  }

  get isFiltered() {
    return this.list.filterRules?.length > 0
  }

  getTitle() {
    let title = this.list.activeSavedViewTitle
    if (title && this.savedViewIsModified) {
      title += '*'
    } else if (!title) {
      title = $localize`File Explorer`
    }
    return title
  }

  getSortFields() {
    return isFullTextFilterRule(this.list.filterRules)
      ? DOCUMENT_SORT_FIELDS_FULLTEXT
      : DOCUMENT_SORT_FIELDS
  }

  set listSortReverse(reverse: boolean) {
    this.list.sortReverse = reverse
  }

  get listSortReverse(): boolean {
    return this.list.sortReverse
  }

  setSortField(field: string) {
    this.list.sortField = field
  }

  onSort(event: SortEvent) {
    this.list.setSort(event.column, event.reverse)
  }

  get isBulkEditing(): boolean {
    return this.list.selected.size > 0
  }

  saveDisplayMode() {
    localStorage.setItem('document-list:displayMode', this.displayMode)
  }

  ngOnInit(): void {
    if (localStorage.getItem('document-list:displayMode') != null) {
      this.displayMode = localStorage.getItem('document-list:displayMode')
    }

    this.consumerStatusService
      .onDocumentConsumptionFinished()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.list.reload()
      })

    this.route.queryParamMap
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((queryParams) => {
        console.log('query params updated:', queryParams)
        this.list.loadFromQueryParams(queryParams)
        this.unmodifiedFilterRules = []
      })
  }

  ngOnDestroy() {
    // unsubscribes all
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }

  clickPathPart(index: number) {
    const pathUntilPart = this.folderPath
      .split('/')
      .slice(0, index + 1)
      .join('/')
    this.list.getStoragePathByPath(pathUntilPart).subscribe((storagePath) => {
      this.router.navigate(['explorer'], {
        queryParams: { spid: storagePath.id },
      })
    })
  }

  openDocumentDetail(storagePath: PaperlessStoragePath) {
    this.router.navigate(['explorer'], {
      queryParams: { spid: storagePath.id },
    })
  }

  toggleSelected(document: PaperlessDocument, event: MouseEvent): void {
    if (!event.shiftKey) this.list.toggleSelected(document)
    else this.list.selectRangeTo(document)
  }

  clickTag(tagID: number) {
    this.list.selectNone()
    this.filterEditor.toggleTag(tagID)
  }

  clickCorrespondent(correspondentID: number) {
    this.list.selectNone()
    this.filterEditor.toggleCorrespondent(correspondentID)
  }

  clickDocumentType(documentTypeID: number) {
    this.list.selectNone()
    this.filterEditor.toggleDocumentType(documentTypeID)
  }

  clickStoragePath(storagePathID: number) {
    this.list.selectNone()
    this.filterEditor.toggleStoragePath(storagePathID)
  }

  clickMoreLike(documentID: number) {
    this.list.quickFilter([
      { rule_type: FILTER_FULLTEXT_MORELIKE, value: documentID.toString() },
    ])
  }

  trackByDocumentId(index, item: PaperlessDocument) {
    return item.id
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }
}
