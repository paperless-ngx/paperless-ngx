import { Injectable, inject } from '@angular/core'
import { ParamMap, Router, UrlTree } from '@angular/router'
import { Observable, Subject, takeUntil } from 'rxjs'
import {
  DEFAULT_DISPLAY_FIELDS,
  DisplayField,
  DisplayMode,
  Document,
} from '../data/document'
import { FilterRule } from '../data/filter-rule'
import { DocumentResults, SelectionData } from '../data/results'
import { SavedView } from '../data/saved-view'
import { DOCUMENT_LIST_SERVICE } from '../data/storage-keys'
import { SETTINGS_KEYS } from '../data/ui-settings'
import {
  cloneFilterRules,
  filterRulesDiffer,
  isFullTextFilterRule,
} from '../utils/filter-rules'
import { paramsFromViewState, paramsToViewState } from '../utils/query-params'
import { DocumentService } from './rest/document.service'
import { SettingsService } from './settings.service'

const LIST_DEFAULT_DISPLAY_FIELDS: DisplayField[] = DEFAULT_DISPLAY_FIELDS.map(
  (f) => f.id
).filter((f) => f !== DisplayField.ADDED)

const RESTORABLE_LIST_VIEW_STATE_KEYS: (keyof ListViewState)[] = [
  'title',
  'documents',
  'currentPage',
  'collectionSize',
  'sortField',
  'sortReverse',
  'filterRules',
  'selected',
  'pageSize',
  'displayMode',
  'displayFields',
]

/**
 * Captures the current state of the list view.
 */
export interface ListViewState {
  /**
   * Title of the document list view. Either "Documents" (localized) or the name of a saved view.
   */
  title?: string

  /**
   * Current paginated list of documents displayed.
   */
  documents?: Document[]

  currentPage: number

  /**
   * Total amount of documents with the current filter rules. Used to calculate the number of pages.
   */
  collectionSize?: number

  /**
   * Currently selected sort field.
   */
  sortField: string

  /**
   * True if the list is sorted in reverse.
   */
  sortReverse: boolean

  /**
   * Filter rules for the current list view.
   */
  filterRules: FilterRule[]

  /**
   * Contains the IDs of all selected documents.
   */
  selected?: Set<number>

  /**
   * True if the full filtered result set is selected.
   */
  allSelected?: boolean

  /**
   * The page size of the list view.
   */
  pageSize?: number

  /**
   * Display mode of the list view.
   */
  displayMode?: DisplayMode

  /**
   * The fields to display in the document list.
   */
  displayFields?: DisplayField[]
}

/**
 * This service manages the document list which is displayed using the document list view.
 *
 * This service also serves saved views by transparently switching between the document list
 * and saved views on request. See below.
 */
@Injectable({
  providedIn: 'root',
})
export class DocumentListViewService {
  private documentService = inject(DocumentService)
  private settings = inject(SettingsService)
  private router = inject(Router)

  isReloading: boolean = false
  initialized: boolean = false
  error: string = null

  rangeSelectionAnchorIndex: number
  lastRangeSelectionToIndex: number

  selectionData?: SelectionData

  private unsubscribeNotifier: Subject<any> = new Subject()

  private listViewStates: Map<number, ListViewState> = new Map()

  private _activeSavedViewId: number = null

  private displayFieldsInitialized: boolean = false

  private restoreListViewState(savedState: unknown): ListViewState {
    const newState = this.defaultListViewState()

    if (
      !savedState ||
      typeof savedState !== 'object' ||
      Array.isArray(savedState)
    ) {
      return newState
    }

    const parsedState = savedState as Partial<
      Record<keyof ListViewState, unknown>
    >
    const mutableState = newState as Record<keyof ListViewState, unknown>

    for (const key of RESTORABLE_LIST_VIEW_STATE_KEYS) {
      const value = parsedState[key]
      if (value != null) {
        mutableState[key] = value
      }
    }

    return newState
  }

  get activeSavedViewId() {
    return this._activeSavedViewId
  }

  get activeSavedViewTitle() {
    return this.activeListViewState.title
  }

  constructor() {
    let documentListViewConfigJson = localStorage.getItem(
      DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG
    )
    if (documentListViewConfigJson) {
      try {
        let savedState: ListViewState = JSON.parse(documentListViewConfigJson)
        let newState = this.restoreListViewState(savedState)
        this.listViewStates.set(null, newState)
      } catch (e) {
        localStorage.removeItem(DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG)
      }
    }

    this.settings.displayFieldsInit.subscribe(() => {
      this.displayFieldsInitialized = true
      if (this.activeListViewState.displayFields) {
        this.activeListViewState.displayFields =
          this.activeListViewState.displayFields.filter(
            (field) =>
              this.settings.allDisplayFields.find((f) => f.id === field) !==
              undefined
          )
        this.saveDocumentListView()
      }
    })
  }

  private defaultListViewState(): ListViewState {
    return {
      title: null,
      documents: [],
      currentPage: 1,
      collectionSize: null,
      sortField: 'created',
      sortReverse: true,
      filterRules: [],
      selected: new Set<number>(),
      allSelected: false,
    }
  }

  private syncSelectedToCurrentPage() {
    if (!this.allSelected) {
      return
    }

    this.selected.clear()
    this.documents?.forEach((doc) => this.selected.add(doc.id))

    if (!this.collectionSize) {
      this.selectNone()
    }
  }

  private get activeListViewState() {
    if (!this.listViewStates.has(this._activeSavedViewId)) {
      this.listViewStates.set(
        this._activeSavedViewId,
        this.defaultListViewState()
      )
    }
    return this.listViewStates.get(this._activeSavedViewId)
  }

  public cancelPending(): void {
    this.unsubscribeNotifier.next(true)
  }

  activateSavedView(view: SavedView) {
    this.rangeSelectionAnchorIndex = this.lastRangeSelectionToIndex = null
    if (view) {
      this._activeSavedViewId = view.id
      this.loadSavedView(view)
    } else {
      this._activeSavedViewId = null
    }
  }

  activateSavedViewWithQueryParams(view: SavedView, queryParams: ParamMap) {
    const viewState = paramsToViewState(queryParams)
    this.activateSavedView(view)
    this.currentPage = viewState.currentPage
  }

  loadSavedView(view: SavedView, closeCurrentView: boolean = false) {
    if (closeCurrentView) {
      this._activeSavedViewId = null
    }

    this.activeListViewState.filterRules = cloneFilterRules(view.filter_rules)
    this.activeListViewState.sortField = view.sort_field
    this.activeListViewState.sortReverse = view.sort_reverse
    if (this._activeSavedViewId) {
      this.activeListViewState.title = view.name
    }
    this.activeListViewState.displayMode = view.display_mode
    this.activeListViewState.pageSize = view.page_size
    this.activeListViewState.displayFields = view.display_fields

    this.reduceSelectionToFilter()

    if (!this.router.routerState.snapshot.url.includes('/view/')) {
      this.router.navigate(['view', view.id])
    }
  }

  loadFromQueryParams(queryParams: ParamMap) {
    const paramsEmpty: boolean = queryParams.keys.length == 0
    let newState: ListViewState = this.listViewStates.get(
      this._activeSavedViewId
    )
    if (!paramsEmpty) newState = paramsToViewState(queryParams)
    if (newState == undefined) newState = this.defaultListViewState() // if nothing in local storage

    // only reload if things have changed
    if (
      !this.initialized ||
      paramsEmpty ||
      this.activeListViewState.sortField !== newState.sortField ||
      this.activeListViewState.sortReverse !== newState.sortReverse ||
      this.activeListViewState.currentPage !== newState.currentPage ||
      filterRulesDiffer(
        this.activeListViewState.filterRules,
        newState.filterRules
      )
    ) {
      this.activeListViewState.filterRules = newState.filterRules
      this.activeListViewState.sortField = newState.sortField
      this.activeListViewState.sortReverse = newState.sortReverse
      this.activeListViewState.currentPage = newState.currentPage
      this.reload(null, paramsEmpty) // update the params if there aren't any
    }
  }

  reload(onFinish?, updateQueryParams: boolean = true) {
    this.cancelPending()
    this.isReloading = true
    this.error = null
    let activeListViewState = this.activeListViewState
    this.documentService
      .listFiltered(
        activeListViewState.currentPage,
        activeListViewState.pageSize ?? this.pageSize,
        activeListViewState.sortField,
        activeListViewState.sortReverse,
        activeListViewState.filterRules,
        { truncate_content: true, include_selection_data: true }
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          const resultWithSelectionData = result as DocumentResults
          this.initialized = true
          this.isReloading = false
          activeListViewState.collectionSize = result.count
          activeListViewState.documents = result.results
          this.selectionData = resultWithSelectionData.selection_data ?? null
          this.syncSelectedToCurrentPage()

          if (updateQueryParams && !this._activeSavedViewId) {
            let base = ['/documents']
            this.router.navigate(base, {
              queryParams: paramsFromViewState(activeListViewState),
              replaceUrl: !this.router.routerState.snapshot.url.includes('?'), // in case navigating from params-less /documents
            })
          } else if (this._activeSavedViewId) {
            this.router.navigate([], {
              queryParams: paramsFromViewState(activeListViewState, true),
              queryParamsHandling: 'merge',
            })
          }

          if (onFinish) {
            onFinish()
          }
          this.rangeSelectionAnchorIndex = this.lastRangeSelectionToIndex = null
        },
        error: (error) => {
          this.isReloading = false
          if (activeListViewState.currentPage != 1 && error.status == 404) {
            // this happens when applying a filter: the current page might not be available anymore due to the reduced result set.
            activeListViewState.currentPage = 1
            this.reload()
          } else if (
            activeListViewState.sortField.indexOf('custom_field') === 0 &&
            this.settings.allDisplayFields.find(
              (f) => f.id === activeListViewState.sortField
            ) === undefined
          ) {
            // e.g. field was deleted
            this.sortField = 'created'
          } else {
            this.selectionData = null
            let errorMessage
            if (
              typeof error.error === 'object' &&
              Object.keys(error.error).length > 0
            ) {
              // e.g. { archive_serial_number: Array<string> }
              errorMessage = Object.keys(error.error)
                .map((fieldName) => {
                  const fieldNameBase = fieldName.split('__')[0]
                  const fieldError: Array<string> = error.error[fieldName]
                  return `${
                    this.sortFields.find(
                      (f) => f.field?.split('__')[0] == fieldNameBase
                    )?.name ?? fieldNameBase
                  }: ${fieldError[0]}`
                })
                .join(', ')
            } else {
              errorMessage = error.error
            }
            this.error = errorMessage
          }
        },
      })
  }

  setFilterRules(filterRules: FilterRule[], resetPage: boolean = false) {
    if (
      !isFullTextFilterRule(filterRules) &&
      this.activeListViewState.sortField == 'score'
    ) {
      this.activeListViewState.sortField = 'created'
    }
    this.activeListViewState.filterRules = filterRules
    if (resetPage) {
      this.activeListViewState.currentPage = 1
    }
    this.reload()
    this.reduceSelectionToFilter()
    this.saveDocumentListView()
  }

  get filterRules(): FilterRule[] {
    return this.activeListViewState.filterRules
  }

  get sortFields(): any[] {
    return this.documentService.sortFields
  }

  get sortFieldsFullText(): any[] {
    return this.documentService.sortFieldsFullText
  }

  set sortField(field: string) {
    this.activeListViewState.sortField = field
    this.reload()
    this.saveDocumentListView()
  }

  get sortField(): string {
    return this.activeListViewState.sortField
  }

  set sortReverse(reverse: boolean) {
    this.activeListViewState.sortReverse = reverse
    this.reload()
    this.saveDocumentListView()
  }

  get sortReverse(): boolean {
    return this.activeListViewState.sortReverse
  }

  get collectionSize(): number {
    return this.activeListViewState.collectionSize
  }

  get currentPage(): number {
    return this.activeListViewState.currentPage
  }

  set currentPage(page: number) {
    if (this.activeListViewState.currentPage == page) return
    this.activeListViewState.currentPage = page
    this.reload()
    this.saveDocumentListView()
  }

  get documents(): Document[] {
    return this.activeListViewState.documents
  }

  get selected(): Set<number> {
    return this.activeListViewState.selected
  }

  get allSelected(): boolean {
    return this.activeListViewState.allSelected ?? false
  }

  get selectedCount(): number {
    return this.allSelected
      ? (this.collectionSize ?? this.selected.size)
      : this.selected.size
  }

  get hasSelection(): boolean {
    return this.allSelected || this.selected.size > 0
  }

  setSort(field: string, reverse: boolean) {
    this.activeListViewState.sortField = field
    this.activeListViewState.sortReverse = reverse
    this.reload()
    this.saveDocumentListView()
  }

  set displayMode(mode: DisplayMode) {
    this.activeListViewState.displayMode = mode
    this.saveDocumentListView()
  }

  get displayMode(): DisplayMode {
    const mode = this.activeListViewState.displayMode ?? DisplayMode.SMALL_CARDS
    if (mode === ('details' as any)) {
      // legacy
      return DisplayMode.TABLE
    }
    return mode
  }

  set pageSize(size: number) {
    this.activeListViewState.pageSize = size
    this.reload()
    this.saveDocumentListView()
  }

  get pageSize(): number {
    return (
      this.activeListViewState.pageSize ??
      this.settings.get(SETTINGS_KEYS.DOCUMENT_LIST_SIZE)
    )
  }

  get displayFields(): DisplayField[] {
    return this.activeListViewState.displayFields ?? LIST_DEFAULT_DISPLAY_FIELDS
  }

  set displayFields(fields: DisplayField[]) {
    this.activeListViewState.displayFields = this.displayFieldsInitialized
      ? fields?.filter(
          (field) =>
            this.settings.allDisplayFields.find((f) => f.id === field) !==
            undefined
        )
      : fields
    this.saveDocumentListView()
  }

  private saveDocumentListView() {
    if (this._activeSavedViewId == null) {
      let savedState: ListViewState = {
        collectionSize: this.activeListViewState.collectionSize,
        currentPage: this.activeListViewState.currentPage,
        filterRules: this.activeListViewState.filterRules,
        sortField: this.activeListViewState.sortField,
        sortReverse: this.activeListViewState.sortReverse,
        displayMode: this.activeListViewState.displayMode,
        displayFields: this.activeListViewState.displayFields,
      }
      localStorage.setItem(
        DOCUMENT_LIST_SERVICE.CURRENT_VIEW_CONFIG,
        JSON.stringify(savedState)
      )
    }
  }

  quickFilter(filterRules: FilterRule[]) {
    this._activeSavedViewId = null
    this.setFilterRules(filterRules)
    this.router.navigate(['documents'])
  }

  getQuickFilterUrl(filterRules: FilterRule[]): UrlTree {
    const defaultState = {
      ...this.defaultListViewState(),
      ...this.listViewStates.get(null),
      filterRules,
    }
    const params = paramsFromViewState(defaultState)
    return this.router.createUrlTree(['/documents'], {
      queryParams: params,
    })
  }

  getLastPage(): number {
    return Math.ceil(this.collectionSize / this.pageSize)
  }

  hasNext(doc: number) {
    if (this.documents) {
      let index = this.documents.findIndex((d) => d.id == doc)
      return (
        index != -1 &&
        (this.currentPage < this.getLastPage() ||
          index + 1 < this.documents.length)
      )
    }
  }

  hasPrevious(doc: number) {
    if (this.documents) {
      let index = this.documents.findIndex((d) => d.id == doc)
      return index != -1 && !(index == 0 && this.currentPage == 1)
    }
  }

  getNext(currentDocId: number): Observable<number> {
    return new Observable((nextDocId) => {
      if (this.documents != null) {
        let index = this.documents.findIndex((d) => d.id == currentDocId)

        if (index != -1 && index + 1 < this.documents.length) {
          nextDocId.next(this.documents[index + 1].id)
          nextDocId.complete()
        } else if (index != -1 && this.currentPage < this.getLastPage()) {
          this.currentPage += 1
          this.reload(() => {
            nextDocId.next(this.documents[0].id)
            nextDocId.complete()
          })
        } else {
          nextDocId.complete()
        }
      } else {
        nextDocId.complete()
      }
    })
  }

  getPrevious(currentDocId: number): Observable<number> {
    return new Observable((prevDocId) => {
      if (this.documents != null) {
        let index = this.documents.findIndex((d) => d.id == currentDocId)

        if (index != 0) {
          prevDocId.next(this.documents[index - 1].id)
          prevDocId.complete()
        } else if (this.currentPage > 1) {
          this.currentPage -= 1
          this.reload(() => {
            prevDocId.next(this.documents[this.documents.length - 1].id)
            prevDocId.complete()
          })
        } else {
          prevDocId.complete()
        }
      } else {
        prevDocId.complete()
      }
    })
  }

  selectNone() {
    this.activeListViewState.allSelected = false
    this.selected.clear()
    this.rangeSelectionAnchorIndex = this.lastRangeSelectionToIndex = null
  }

  reduceSelectionToFilter() {
    if (this.allSelected) {
      return
    }

    if (this.selected.size > 0) {
      this.documentService
        .listAllFilteredIds(this.filterRules)
        .subscribe((ids) => {
          for (let id of this.selected) {
            if (!ids.includes(id)) {
              this.selected.delete(id)
            }
          }
        })
    }
  }

  selectAll() {
    this.activeListViewState.allSelected = true
    this.syncSelectedToCurrentPage()
  }

  selectPage() {
    this.activeListViewState.allSelected = false
    this.selected.clear()
    this.documents.forEach((doc) => {
      this.selected.add(doc.id)
    })
  }

  isSelected(d: Document) {
    return this.allSelected || this.selected.has(d.id)
  }

  toggleSelected(d: Document): void {
    if (this.allSelected) {
      this.activeListViewState.allSelected = false
    }
    if (this.selected.has(d.id)) this.selected.delete(d.id)
    else this.selected.add(d.id)
    this.rangeSelectionAnchorIndex = this.documentIndexInCurrentView(d.id)
    this.lastRangeSelectionToIndex = null
  }

  selectRangeTo(d: Document) {
    if (this.allSelected) {
      this.activeListViewState.allSelected = false
    }

    if (this.rangeSelectionAnchorIndex !== null) {
      const documentToIndex = this.documentIndexInCurrentView(d.id)
      const fromIndex = Math.min(
        this.rangeSelectionAnchorIndex,
        documentToIndex
      )
      const toIndex = Math.max(this.rangeSelectionAnchorIndex, documentToIndex)

      if (this.lastRangeSelectionToIndex !== null) {
        // revert the old selection
        this.documents
          .slice(
            Math.min(
              this.rangeSelectionAnchorIndex,
              this.lastRangeSelectionToIndex
            ),
            Math.max(
              this.rangeSelectionAnchorIndex,
              this.lastRangeSelectionToIndex
            ) + 1
          )
          .forEach((d) => {
            this.selected.delete(d.id)
          })
      }

      this.documents.slice(fromIndex, toIndex + 1).forEach((d) => {
        this.selected.add(d.id)
      })
      this.lastRangeSelectionToIndex = documentToIndex
    } else {
      // e.g. shift key but was first click
      this.toggleSelected(d)
    }
  }

  documentIndexInCurrentView(documentID: number): number {
    return this.documents.map((d) => d.id).indexOf(documentID)
  }
}
