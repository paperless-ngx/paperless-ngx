import { AsyncPipe, NgClass, NgTemplateOutlet } from '@angular/common'
import {
  Component,
  inject,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  ActivatedRoute,
  convertToParamMap,
  Router,
  RouterModule,
} from '@angular/router'
import {
  NgbDropdownModule,
  NgbModal,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TourNgBootstrap } from 'ngx-ui-tour-ng-bootstrap'
import { filter, first, map, Subject, switchMap, takeUntil } from 'rxjs'
import {
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  DisplayMode,
  Document,
} from 'src/app/data/document'
import { FilterRule } from 'src/app/data/filter-rule'
import { FILTER_FULLTEXT_MORELIKE } from 'src/app/data/filter-rule-type'
import { SavedView } from 'src/app/data/saved-view'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  SortableDirective,
  SortEvent,
} from 'src/app/directives/sortable.directive'
import { CorrespondentNamePipe } from 'src/app/pipes/correspondent-name.pipe'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentTitlePipe } from 'src/app/pipes/document-title.pipe'
import { DocumentTypeNamePipe } from 'src/app/pipes/document-type-name.pipe'
import { StoragePathNamePipe } from 'src/app/pipes/storage-path-name.pipe'
import { UsernamePipe } from 'src/app/pipes/username.pipe'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { HotKeyService } from 'src/app/services/hot-key.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { WebsocketStatusService } from 'src/app/services/websocket-status.service'
import {
  filterRulesDiffer,
  isFullTextFilterRule,
} from 'src/app/utils/filter-rules'
import { ClearableBadgeComponent } from '../common/clearable-badge/clearable-badge.component'
import { CustomFieldDisplayComponent } from '../common/custom-field-display/custom-field-display.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { PreviewPopupComponent } from '../common/preview-popup/preview-popup.component'
import { TagComponent } from '../common/tag/tag.component'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { BulkEditorComponent } from './bulk-editor/bulk-editor.component'
import { DocumentCardLargeComponent } from './document-card-large/document-card-large.component'
import { DocumentCardSmallComponent } from './document-card-small/document-card-small.component'
import { FilterEditorComponent } from './filter-editor/filter-editor.component'
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component'

@Component({
  selector: 'pngx-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.scss'],
  imports: [
    ClearableBadgeComponent,
    CustomFieldDisplayComponent,
    PageHeaderComponent,
    BulkEditorComponent,
    FilterEditorComponent,
    DocumentCardSmallComponent,
    DocumentCardLargeComponent,
    PreviewPopupComponent,
    TagComponent,
    CustomDatePipe,
    DocumentTitlePipe,
    IfPermissionsDirective,
    SortableDirective,
    UsernamePipe,
    CorrespondentNamePipe,
    DocumentTypeNamePipe,
    StoragePathNamePipe,
    NgxBootstrapIconsModule,
    AsyncPipe,
    FormsModule,
    ReactiveFormsModule,
    NgTemplateOutlet,
    NgbDropdownModule,
    NgbPaginationModule,
    NgClass,
    RouterModule,
    TourNgBootstrap,
  ],
})
export class DocumentListComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  list = inject(DocumentListViewService)
  savedViewService = inject(SavedViewService)
  route = inject(ActivatedRoute)
  private router = inject(Router)
  private toastService = inject(ToastService)
  private modalService = inject(NgbModal)
  private websocketStatusService = inject(WebsocketStatusService)
  openDocumentsService = inject(OpenDocumentsService)
  settingsService = inject(SettingsService)
  private hotKeyService = inject(HotKeyService)
  permissionService = inject(PermissionsService)

  DisplayField = DisplayField
  DisplayMode = DisplayMode

  @ViewChild('filterEditor')
  private filterEditor: FilterEditorComponent

  @ViewChildren(SortableDirective) headers: QueryList<SortableDirective>

  get activeDisplayFields(): DisplayField[] {
    return this.list.displayFields
  }

  set activeDisplayFields(fields: DisplayField[]) {
    this.list.displayFields = fields
    this.updateDisplayCustomFields()
  }
  activeDisplayCustomFields: Set<string> = new Set()

  public updateDisplayCustomFields() {
    this.activeDisplayCustomFields = new Set(
      Array.from(this.activeDisplayFields).filter(
        (field) =>
          typeof field === 'string' &&
          field.startsWith(DisplayField.CUSTOM_FIELD)
      )
    )
  }

  unmodifiedFilterRules: FilterRule[] = []
  private unmodifiedSavedView: SavedView

  private unsubscribeNotifier: Subject<any> = new Subject()

  get savedViewIsModified(): boolean {
    if (!this.list.activeSavedViewId || !this.unmodifiedSavedView) return false
    else {
      return (
        this.unmodifiedSavedView.sort_field !== this.list.sortField ||
        this.unmodifiedSavedView.sort_reverse !== this.list.sortReverse ||
        (this.unmodifiedSavedView.page_size &&
          this.unmodifiedSavedView.page_size !== this.list.pageSize) ||
        (this.unmodifiedSavedView.display_mode &&
          this.unmodifiedSavedView.display_mode !== this.list.displayMode) ||
        // if the saved view has no display mode, we assume it's small cards
        (!this.unmodifiedSavedView.display_mode &&
          this.list.displayMode !== DisplayMode.SMALL_CARDS) ||
        (this.unmodifiedSavedView.display_fields &&
          this.unmodifiedSavedView.display_fields.join(',') !==
            this.activeDisplayFields.join(',')) ||
        (!this.unmodifiedSavedView.display_fields &&
          this.activeDisplayFields.join(',') !==
            DEFAULT_DISPLAY_FIELDS.filter((f) => f.id !== DisplayField.ADDED)
              .map((f) => f.id)
              .join(',')) ||
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
      ? this.list.sortFieldsFullText
      : this.list.sortFields
  }

  set listSortReverse(reverse: boolean) {
    this.list.sortReverse = reverse
  }

  get listSortReverse(): boolean {
    return this.list.sortReverse
  }

  onSort(event: SortEvent) {
    this.list.setSort(event.column, event.reverse)
  }

  get isBulkEditing(): boolean {
    return this.list.selected.size > 0
  }

  toggleDisplayField(field: DisplayField) {
    if (this.activeDisplayFields.includes(field)) {
      this.activeDisplayFields = this.activeDisplayFields.filter(
        (f) => f !== field
      )
    } else {
      this.activeDisplayFields = [...this.activeDisplayFields, field]
    }
    this.updateDisplayCustomFields()
  }

  public getDisplayCustomFieldTitle(field: string) {
    return this.settingsService.allDisplayFields.find((f) => f.id === field)
      ?.name
  }

  ngOnInit(): void {
    this.websocketStatusService
      .onDocumentConsumptionFinished()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.list.reload()
      })

    this.websocketStatusService.onDocumentDeleted().subscribe(() => {
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
        this.list.reload(() => {
          this.savedViewService.setDocumentCount(view, this.list.collectionSize)
        })
        this.updateDisplayCustomFields()
        this.unmodifiedFilterRules = view.filter_rules
      })

    this.route.queryParamMap
      .pipe(
        filter(() => !this.route.snapshot.paramMap.has('id')), // only when not on /view/id
        takeUntil(this.unsubscribeNotifier)
      )
      .subscribe((queryParams) => {
        this.updateDisplayCustomFields()
        if (queryParams.has('view')) {
          // loading a saved view on /documents
          this.loadViewConfig(parseInt(queryParams.get('view')))
        } else {
          this.list.activateSavedView(null)
          this.list.loadFromQueryParams(queryParams)
          this.unmodifiedFilterRules = []
        }
      })

    this.hotKeyService
      .addShortcut({
        keys: 'escape',
        description: $localize`Reset filters / selection`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (this.list.selected.size > 0) {
          this.list.selectNone()
        } else if (this.isFiltered) {
          this.filterEditor.resetSelected()
        }
      })

    this.hotKeyService
      .addShortcut({ keys: 'a', description: $localize`Select all` })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.list.selectAll()
      })

    this.hotKeyService
      .addShortcut({ keys: 'p', description: $localize`Select page` })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.list.selectPage()
      })

    this.hotKeyService
      .addShortcut({
        keys: 'o',
        description: $localize`Open first [selected] document`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (this.list.documents.length > 0) {
          if (this.list.selected.size > 0) {
            this.openDocumentDetail(Array.from(this.list.selected)[0])
          } else {
            this.openDocumentDetail(this.list.documents[0])
          }
        }
      })

    this.hotKeyService
      .addShortcut({
        keys: 'control.arrowleft',
        description: $localize`Previous page`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (this.list.currentPage > 1) {
          this.list.currentPage--
        }
      })

    this.hotKeyService
      .addShortcut({
        keys: 'control.arrowright',
        description: $localize`Next page`,
      })
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        if (this.list.currentPage < this.list.getLastPage()) {
          this.list.currentPage++
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
        display_mode: this.list.displayMode,
        display_fields: this.activeDisplayFields,
      }
      this.savedViewService
        .patch(savedView)
        .pipe(first())
        .subscribe({
          next: (view) => {
            this.unmodifiedSavedView = view
            this.toastService.showInfo(
              $localize`View "${this.list.activeSavedViewTitle}" saved successfully.`
            )
            this.unmodifiedFilterRules = this.list.filterRules
          },
          error: (err) => {
            this.toastService.showError(
              $localize`Failed to save view "${this.list.activeSavedViewTitle}".`,
              err
            )
          },
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
        this.list.reload(() => {
          this.savedViewService.setDocumentCount(view, this.list.collectionSize)
        })
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
        display_mode: this.list.displayMode,
        display_fields: this.activeDisplayFields,
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

  openDocumentDetail(document: Document | number) {
    this.router.navigate([
      'documents',
      typeof document === 'number' ? document : document.id,
    ])
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

  get notesEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.NOTES_ENABLED)
  }

  resetFilters() {
    this.filterEditor.resetSelected()
  }
}
