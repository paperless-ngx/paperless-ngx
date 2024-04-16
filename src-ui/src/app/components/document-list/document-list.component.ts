import {
  Component,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core'
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { filter, first, map, Subject, switchMap, takeUntil } from 'rxjs'
import { FilterRule } from 'src/app/data/filter-rule'
import {
  filterRulesDiffer,
  isFullTextFilterRule,
} from 'src/app/utils/filter-rules'
import { FILTER_FULLTEXT_MORELIKE } from 'src/app/data/filter-rule-type'
import { Document } from 'src/app/data/document'
import { SavedView } from 'src/app/data/saved-view'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import {
  SortableDirective,
  SortEvent,
} from 'src/app/directives/sortable.directive'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import {
  DOCUMENT_SORT_FIELDS,
  DOCUMENT_SORT_FIELDS_FULLTEXT,
} from 'src/app/services/rest/document.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { FilterEditorComponent } from './filter-editor/filter-editor.component'
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component'

@Component({
  selector: 'pngx-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.scss'],
})
export class DocumentListComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  constructor(
    public list: DocumentListViewService,
    public savedViewService: SavedViewService,
    public route: ActivatedRoute,
    private router: Router,
    private toastService: ToastService,
    private modalService: NgbModal,
    private consumerStatusService: ConsumerStatusService,
    public openDocumentsService: OpenDocumentsService,
    private settingsService: SettingsService,
    public permissionService: PermissionsService
  ) {
    super()
  }

  @ViewChild('filterEditor')
  private filterEditor: FilterEditorComponent

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>

  displayMode = 'smallCards' // largeCards, smallCards, details

  unmodifiedFilterRules: FilterRule[] = []
  private unmodifiedSavedView: SavedView

  private unsubscribeNotifier: Subject<any> = new Subject()

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
    return !!this.filterEditor?.rulesModified
  }

  getTitle() {
    let title = this.list.activeSavedViewTitle
    if (title && this.savedViewIsModified) {
      title += '*'
    } else if (!title) {
      title = $localize`Documents`
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

    this.route.paramMap
      .pipe(
        filter((params) => params.has('id')), // only on saved view e.g. /view/id
        switchMap((params) => {
          return this.savedViewService
            .getCached(+params.get('id'))
            .pipe(map((view) => ({ view })))
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ view }) => {
        if (!view) {
          this.router.navigate(['404'], {
            replaceUrl: true,
          })
          return
        }
        this.unmodifiedSavedView = view
        this.list.activateSavedViewWithQueryParams(
          view,
          convertToParamMap(this.route.snapshot.queryParams)
        )
        this.list.reload()
        this.unmodifiedFilterRules = view.filter_rules
      })

    this.route.queryParamMap
      .pipe(
        filter(() => !this.route.snapshot.paramMap.has('id')), // only when not on /view/id
        takeUntil(this.unsubscribeNotifier)
      )
      .subscribe((queryParams) => {
        if (queryParams.has('view')) {
          // loading a saved view on /documents
          this.loadViewConfig(parseInt(queryParams.get('view')))
        } else {
          this.list.activateSavedView(null)
          this.list.loadFromQueryParams(queryParams)
          this.unmodifiedFilterRules = []
        }
      })
  }

  ngOnDestroy() {
    this.list.cancelPending()
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }

  saveViewConfig() {
    if (this.list.activeSavedViewId != null) {
      let savedView: SavedView = {
        id: this.list.activeSavedViewId,
        filter_rules: this.list.filterRules,
        sort_field: this.list.sortField,
        sort_reverse: this.list.sortReverse,
      }
      this.savedViewService
        .patch(savedView)
        .pipe(first())
        .subscribe((view) => {
          this.unmodifiedSavedView = view
          this.toastService.showInfo(
            $localize`View "${this.list.activeSavedViewTitle}" saved successfully.`
          )
          this.unmodifiedFilterRules = this.list.filterRules
        })
    }
  }

  loadViewConfig(viewID: number) {
    this.savedViewService
      .getCached(viewID)
      .pipe(first())
      .subscribe((view) => {
        this.unmodifiedSavedView = view
        this.list.activateSavedView(view)
        this.list.reload()
      })
  }

  saveViewConfigAs() {
    let modal = this.modalService.open(SaveViewConfigDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.defaultName = this.filterEditor.generateFilterName()
    modal.componentInstance.saveClicked.pipe(first()).subscribe((formValue) => {
      modal.componentInstance.buttonsEnabled = false
      let savedView: SavedView = {
        name: formValue.name,
        show_on_dashboard: formValue.showOnDashboard,
        show_in_sidebar: formValue.showInSideBar,
        filter_rules: this.list.filterRules,
        sort_reverse: this.list.sortReverse,
        sort_field: this.list.sortField,
      }

      this.savedViewService
        .create(savedView)
        .pipe(first())
        .subscribe({
          next: () => {
            modal.close()
            this.toastService.showInfo(
              $localize`View "${savedView.name}" created successfully.`
            )
          },
          error: (httpError) => {
            let error = httpError.error
            if (error.filter_rules) {
              error.filter_rules = error.filter_rules.map((r) => r.value)
            }
            modal.componentInstance.error = error
            modal.componentInstance.buttonsEnabled = true
          },
        })
    })
  }

  openDocumentDetail(document: Document) {
    this.router.navigate(['documents', document.id])
  }

  toggleSelected(document: Document, event: MouseEvent): void {
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

  trackByDocumentId(index, item: Document) {
    return item.id
  }

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }

  resetFilters() {
    this.filterEditor.resetSelected()
  }
}
