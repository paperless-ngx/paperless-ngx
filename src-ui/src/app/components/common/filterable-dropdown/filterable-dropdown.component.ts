import {
  CdkVirtualScrollViewport,
  ScrollingModule,
} from '@angular/cdk/scrolling'
import { NgClass } from '@angular/common'
import {
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnInit,
  Output,
  ViewChild,
  inject,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbDropdown, NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, filter, takeUntil } from 'rxjs'
import { NEGATIVE_NULL_FILTER_VALUE } from 'src/app/data/filter-rule-type'
import { MatchingModel } from 'src/app/data/matching-model'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { FilterPipe } from 'src/app/pipes/filter.pipe'
import { HotKeyService } from 'src/app/services/hot-key.service'
import { SelectionDataItem } from 'src/app/services/rest/document.service'
import { pngxPopperOptions } from 'src/app/utils/popper-options'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
import { ClearableBadgeComponent } from '../clearable-badge/clearable-badge.component'
import {
  ToggleableDropdownButtonComponent,
  ToggleableItemState,
} from './toggleable-dropdown-button/toggleable-dropdown-button.component'

export interface ChangedItems {
  itemsToAdd: MatchingModel[]
  itemsToRemove: MatchingModel[]
}

type BranchSummary = {
  items: MatchingModel[]
  firstIndex: number
  special: boolean
  selected: boolean
  hasDocs: boolean
}

export enum LogicalOperator {
  And = 'and',
  Or = 'or',
}

export enum Intersection {
  Include = 'include',
  Exclude = 'exclude',
}

export class FilterableDropdownSelectionModel {
  changed = new Subject<FilterableDropdownSelectionModel>()

  manyToOne = false
  singleSelect = false
  private _logicalOperator: LogicalOperator = LogicalOperator.And
  temporaryLogicalOperator: LogicalOperator = this._logicalOperator
  private _intersection: Intersection = Intersection.Include
  temporaryIntersection: Intersection = this._intersection

  private _documentCounts: SelectionDataItem[] = []
  public documentCountSortingEnabled = false

  public set documentCounts(counts: SelectionDataItem[]) {
    this._documentCounts = counts
    if (this.documentCountSortingEnabled) {
      this.sortItems()
    }
  }

  private _items: MatchingModel[] = []
  get items(): MatchingModel[] {
    return this._items
  }

  set items(items: MatchingModel[]) {
    if (items) {
      this._items = Array.from(items)
      this.sortItems()
      this.setNullItem()
    }
  }

  private setNullItem() {
    if (this.manyToOne && this.logicalOperator === LogicalOperator.Or) {
      if (this._items[0]?.id === null) {
        this._items.shift()
      }
      return
    }

    const item = {
      name: $localize`:Filter drop down element to filter for documents with no correspondent/type/tag assigned:Not assigned`,
      id:
        this.manyToOne || this.intersection === Intersection.Include
          ? null
          : NEGATIVE_NULL_FILTER_VALUE,
    }

    if (
      this._items[0]?.id === null ||
      this._items[0]?.id === NEGATIVE_NULL_FILTER_VALUE
    ) {
      this._items[0] = item
    } else if (this._items) {
      this._items.unshift(item)
    }
  }

  constructor(manyToOne: boolean = false) {
    this.manyToOne = manyToOne
  }

  private sortItems() {
    this._items.sort((a, b) => {
      if (
        (a.id == null && b.id != null) ||
        (a.id == NEGATIVE_NULL_FILTER_VALUE &&
          b.id != NEGATIVE_NULL_FILTER_VALUE)
      ) {
        return -1
      } else if (
        (a.id != null && b.id == null) ||
        (a.id != NEGATIVE_NULL_FILTER_VALUE &&
          b.id == NEGATIVE_NULL_FILTER_VALUE)
      ) {
        return 1
      }

      // Preserve hierarchical order when provided (e.g., Tags)
      const ao = (a as any)['orderIndex']
      const bo = (b as any)['orderIndex']
      if (ao !== undefined && bo !== undefined) {
        return ao - bo
      } else if (
        this.getNonTemporary(a.id) == ToggleableItemState.NotSelected &&
        this.getNonTemporary(b.id) != ToggleableItemState.NotSelected
      ) {
        return 1
      } else if (
        this.getNonTemporary(a.id) != ToggleableItemState.NotSelected &&
        this.getNonTemporary(b.id) == ToggleableItemState.NotSelected
      ) {
        return -1
      } else if (
        this._documentCounts.length &&
        this.getDocumentCount(b.id) === 0 &&
        this.getDocumentCount(a.id) > this.getDocumentCount(b.id)
      ) {
        return -1
      } else if (
        this._documentCounts.length &&
        this.getDocumentCount(a.id) === 0 &&
        this.getDocumentCount(a.id) < this.getDocumentCount(b.id)
      ) {
        return 1
      } else {
        return a.name.localeCompare(b.name)
      }
    })

    if (this._documentCounts.length) {
      this.promoteBranchesWithDocumentCounts()
    }
  }

  private selectionStates = new Map<number, ToggleableItemState>()

  private temporarySelectionStates = new Map<number, ToggleableItemState>()

  getSelectedItems() {
    return this.items.filter(
      (i) =>
        this.temporarySelectionStates.get(i.id) == ToggleableItemState.Selected
    )
  }

  getExcludedItems() {
    return this.items.filter(
      (i) =>
        this.temporarySelectionStates.get(i.id) == ToggleableItemState.Excluded
    )
  }

  set(id: number, state: ToggleableItemState, fireEvent = true) {
    if (state == ToggleableItemState.NotSelected) {
      this.temporarySelectionStates.delete(id)
    } else {
      this.temporarySelectionStates.set(id, state)
    }
    if (fireEvent) {
      this.changed.next(this)
    }
  }

  toggle(id: number, fireEvent = true) {
    let state = this.temporarySelectionStates.get(id)
    if (
      state == undefined ||
      (state != ToggleableItemState.Selected &&
        state != ToggleableItemState.Excluded)
    ) {
      if (this.manyToOne || this.singleSelect) {
        this.temporarySelectionStates.set(id, ToggleableItemState.Selected)

        if (this.singleSelect) {
          for (let key of this.temporarySelectionStates.keys()) {
            if (key != id) {
              this.temporarySelectionStates.delete(key)
            }
          }
        }
      } else {
        let newState =
          this.intersection == Intersection.Include
            ? ToggleableItemState.Selected
            : ToggleableItemState.Excluded
        if (!id) newState = ToggleableItemState.Selected
        if (
          state == ToggleableItemState.Excluded &&
          this.intersection == Intersection.Exclude
        ) {
          newState = ToggleableItemState.NotSelected
        }
        this.temporarySelectionStates.set(id, newState)
      }
    } else if (
      state == ToggleableItemState.Selected ||
      state == ToggleableItemState.Excluded
    ) {
      this.temporarySelectionStates.delete(id)
    }

    if (!id) {
      for (let key of this.temporarySelectionStates.keys()) {
        if (key) {
          this.temporarySelectionStates.delete(key)
        }
      }
    } else {
      this.temporarySelectionStates.delete(null)
    }

    if (fireEvent) {
      this.changed.next(this)
    }
  }

  exclude(id: number, fireEvent: boolean = true) {
    let state = this.temporarySelectionStates.get(id)
    if (id && (state == null || state != ToggleableItemState.Excluded)) {
      this.temporaryLogicalOperator = this._logicalOperator = this.manyToOne
        ? LogicalOperator.And
        : LogicalOperator.Or

      if (this.manyToOne || this.singleSelect) {
        this.temporarySelectionStates.set(id, ToggleableItemState.Excluded)

        if (this.singleSelect) {
          for (let key of this.temporarySelectionStates.keys()) {
            if (key != id) {
              this.temporarySelectionStates.delete(key)
            }
          }
        }
      } else {
        let newState =
          this.intersection == Intersection.Include
            ? ToggleableItemState.Selected
            : ToggleableItemState.Excluded
        if (
          state == ToggleableItemState.Selected &&
          this.intersection == Intersection.Include
        ) {
          newState = ToggleableItemState.NotSelected
        }
        this.temporarySelectionStates.set(id, newState)
      }
    } else if (!id || state == ToggleableItemState.Excluded) {
      this.temporarySelectionStates.delete(id)
    }

    if (fireEvent) {
      this.changed.next(this)
    }
  }

  private getNonTemporary(id: number) {
    return this.selectionStates.get(id) || ToggleableItemState.NotSelected
  }

  get logicalOperator(): LogicalOperator {
    return this.temporaryLogicalOperator
  }

  set logicalOperator(operator: LogicalOperator) {
    this.temporaryLogicalOperator = operator
    this.setNullItem()
  }

  toggleOperator() {
    this.changed.next(this)
  }

  get intersection(): Intersection {
    return this.temporaryIntersection
  }

  set intersection(intersection: Intersection) {
    this.temporaryIntersection = intersection
    this.setNullItem()
  }

  toggleIntersection() {
    if (this.temporarySelectionStates.size === 0) return
    let newState =
      this.intersection == Intersection.Include
        ? ToggleableItemState.Selected
        : ToggleableItemState.Excluded

    this.temporarySelectionStates.forEach((state, key) => {
      if (key === null && this.intersection === Intersection.Exclude) {
        this.temporarySelectionStates.set(NEGATIVE_NULL_FILTER_VALUE, newState)
      } else if (
        key === NEGATIVE_NULL_FILTER_VALUE &&
        this.intersection === Intersection.Include
      ) {
        this.temporarySelectionStates.set(null, newState)
      } else {
        this.temporarySelectionStates.set(key, newState)
      }
    })

    this.changed.next(this)
  }

  get(id: number) {
    return (
      this.temporarySelectionStates.get(id) || ToggleableItemState.NotSelected
    )
  }

  selectionSize() {
    return this.getSelectedItems().length
  }

  get totalCount() {
    return this.getSelectedItems().length + this.getExcludedItems().length
  }

  clear(fireEvent = true) {
    this.temporarySelectionStates.clear()
    this.temporaryLogicalOperator = this._logicalOperator = LogicalOperator.And
    this.temporaryIntersection = this._intersection = Intersection.Include
    this.setNullItem()
    if (fireEvent) {
      this.changed.next(this)
    }
  }

  isDirty() {
    if (
      !Array.from(this.temporarySelectionStates.keys()).every(
        (id) =>
          this.temporarySelectionStates.get(id) == this.selectionStates.get(id)
      )
    ) {
      return true
    } else if (
      !Array.from(this.selectionStates.keys()).every(
        (id) =>
          this.selectionStates.get(id) == this.temporarySelectionStates.get(id)
      )
    ) {
      return true
    } else if (this.temporaryLogicalOperator !== this._logicalOperator) {
      return true
    } else if (this.temporaryIntersection !== this._intersection) {
      return true
    } else {
      return false
    }
  }

  isNoneSelected() {
    return (
      (this.selectionSize() == 1 &&
        this.get(null) == ToggleableItemState.Selected) ||
      (this.intersection == Intersection.Exclude &&
        this.get(NEGATIVE_NULL_FILTER_VALUE) == ToggleableItemState.Excluded)
    )
  }

  getDocumentCount(id: number) {
    return this._documentCounts.find((c) => c.id === id)?.document_count
  }

  private promoteBranchesWithDocumentCounts() {
    const parentById = this.buildParentById()
    const findRootId = this.createRootFinder(parentById)
    const getRootDocCount = this.createRootDocCounter()
    const summaries = this.buildBranchSummaries(findRootId, getRootDocCount)
    const orderedBranches = this.orderBranchesByPriority(summaries)

    this._items = orderedBranches.flatMap((summary) => summary.items)
  }

  private buildParentById(): Map<number, number | null> {
    const parentById = new Map<number, number | null>()

    for (const item of this._items) {
      if (typeof item?.id === 'number') {
        const parentValue = (item as any)['parent']
        parentById.set(
          item.id,
          typeof parentValue === 'number' ? parentValue : null
        )
      }
    }

    return parentById
  }

  private createRootFinder(
    parentById: Map<number, number | null>
  ): (id: number) => number {
    const rootMemo = new Map<number, number>()

    const findRootId = (id: number): number => {
      const cached = rootMemo.get(id)
      if (cached !== undefined) {
        return cached
      }

      const parentId = parentById.get(id)
      if (parentId === undefined || parentId === null) {
        rootMemo.set(id, id)
        return id
      }

      const rootId = findRootId(parentId)
      rootMemo.set(id, rootId)
      return rootId
    }

    return findRootId
  }

  private createRootDocCounter(): (rootId: number) => number {
    const docCountMemo = new Map<number, number>()

    return (rootId: number): number => {
      const cached = docCountMemo.get(rootId)
      if (cached !== undefined) {
        return cached
      }

      const explicit = this.getDocumentCount(rootId)
      if (typeof explicit === 'number') {
        docCountMemo.set(rootId, explicit)
        return explicit
      }

      const rootItem = this._items.find((i) => i.id === rootId)
      const fallback =
        typeof (rootItem as any)?.['document_count'] === 'number'
          ? (rootItem as any)['document_count']
          : 0

      docCountMemo.set(rootId, fallback)
      return fallback
    }
  }

  private buildBranchSummaries(
    findRootId: (id: number) => number,
    getRootDocCount: (rootId: number) => number
  ): Map<string, BranchSummary> {
    const summaries = new Map<string, BranchSummary>()

    for (const [index, item] of this._items.entries()) {
      const { key, special, rootId } = this.describeBranchItem(
        item,
        index,
        findRootId
      )

      let summary = summaries.get(key)
      if (!summary) {
        summary = {
          items: [],
          firstIndex: index,
          special,
          selected: false,
          hasDocs:
            special || rootId === null ? false : getRootDocCount(rootId) > 0,
        }
        summaries.set(key, summary)
      }

      summary.items.push(item)

      if (this.shouldMarkSummarySelected(summary, item)) {
        summary.selected = true
      }
    }

    return summaries
  }

  private describeBranchItem(
    item: MatchingModel,
    index: number,
    findRootId: (id: number) => number
  ): { key: string; special: boolean; rootId: number | null } {
    if (item?.id === null) {
      return { key: 'null', special: true, rootId: null }
    }

    if (item?.id === NEGATIVE_NULL_FILTER_VALUE) {
      return { key: 'neg-null', special: true, rootId: null }
    }

    if (typeof item?.id === 'number') {
      const rootId = findRootId(item.id)
      return { key: `root-${rootId}`, special: false, rootId }
    }

    return { key: `misc-${index}`, special: false, rootId: null }
  }

  private shouldMarkSummarySelected(
    summary: BranchSummary,
    item: MatchingModel
  ): boolean {
    if (summary.special) {
      return false
    }

    if (typeof item?.id !== 'number') {
      return false
    }

    return this.getNonTemporary(item.id) !== ToggleableItemState.NotSelected
  }

  private orderBranchesByPriority(
    summaries: Map<string, BranchSummary>
  ): BranchSummary[] {
    return Array.from(summaries.values()).sort((a, b) => {
      const rankDiff = this.branchRank(a) - this.branchRank(b)
      if (rankDiff !== 0) {
        return rankDiff
      }
      if (a.hasDocs !== b.hasDocs) {
        return a.hasDocs ? -1 : 1
      }
      return a.firstIndex - b.firstIndex
    })
  }

  private branchRank(summary: BranchSummary): number {
    if (summary.special) {
      return -1
    }
    if (summary.selected) {
      return 0
    }
    return 1
  }

  init(map: Map<number, ToggleableItemState>) {
    this.temporarySelectionStates = map
    this.apply()
  }

  apply() {
    this.selectionStates.clear()
    this.temporarySelectionStates.forEach((value, key) => {
      this.selectionStates.set(key, value)
    })
    this._logicalOperator = this.temporaryLogicalOperator
    this._intersection = this.temporaryIntersection
    this.sortItems()
  }

  reset(complete: boolean = false) {
    this.temporarySelectionStates.clear()
    if (complete) {
      this.selectionStates.clear()
    } else {
      this.selectionStates.forEach((value, key) => {
        this.temporarySelectionStates.set(key, value)
      })
    }
  }

  diff(): ChangedItems {
    return {
      itemsToAdd: this.items.filter(
        (item) =>
          this.temporarySelectionStates.get(item.id) ==
            ToggleableItemState.Selected &&
          this.selectionStates.get(item.id) != ToggleableItemState.Selected
      ),
      itemsToRemove: this.items.filter(
        (item) =>
          !this.temporarySelectionStates.has(item.id) &&
          this.selectionStates.has(item.id)
      ),
    }
  }
}

@Component({
  selector: 'pngx-filterable-dropdown',
  templateUrl: './filterable-dropdown.component.html',
  styleUrls: ['./filterable-dropdown.component.scss'],
  imports: [
    ClearableBadgeComponent,
    ToggleableDropdownButtonComponent,
    FilterPipe,
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
    NgbDropdownModule,
    NgClass,
    ScrollingModule,
  ],
})
export class FilterableDropdownComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  public readonly FILTERABLE_BUTTON_HEIGHT_PX = 42

  private filterPipe = inject(FilterPipe)
  private hotkeyService = inject(HotKeyService)

  @ViewChild('listFilterTextInput') listFilterTextInput: ElementRef
  @ViewChild('dropdown') dropdown: NgbDropdown
  @ViewChild('buttonsViewport') buttonsViewport: CdkVirtualScrollViewport

  private get renderedButtons(): Array<HTMLButtonElement> {
    return Array.from(
      this.buttonsViewport.elementRef.nativeElement.querySelectorAll('button')
    )
  }

  public popperOptions = pngxPopperOptions

  filterText: string

  _selectionModel: FilterableDropdownSelectionModel

  get items(): MatchingModel[] {
    return this._selectionModel.items
  }

  @Input({ required: true })
  set selectionModel(model: FilterableDropdownSelectionModel) {
    if (this.selectionModel) {
      this.selectionModel.changed.complete()
      model.items = this.selectionModel.items
      model.manyToOne = this.selectionModel.manyToOne
      model.singleSelect = this._editing && !model.manyToOne
    }
    model.documentCountSortingEnabled = this._editing
    model.changed.subscribe((updatedModel) => {
      this.selectionModelChange.next(updatedModel)
    })
    this._selectionModel = model
  }

  get selectionModel(): FilterableDropdownSelectionModel {
    return this._selectionModel
  }

  @Output()
  selectionModelChange = new EventEmitter<FilterableDropdownSelectionModel>()

  get manyToOne() {
    return this.selectionModel.manyToOne
  }

  @Input()
  title: string

  @Input()
  filterPlaceholder: string = ''

  @Input()
  icon: string

  @Input()
  allowSelectNone: boolean = false

  private _editing = false

  @Input()
  set editing(value: boolean) {
    this._editing = value
    if (this.selectionModel) {
      this.selectionModel.singleSelect =
        this._editing && !this.selectionModel.manyToOne
      this.selectionModel.documentCountSortingEnabled = this._editing
    }
  }

  get editing() {
    return this._editing
  }

  @Input()
  applyOnClose = false

  @Input()
  disabled = false

  @Input()
  createRef: (name) => void

  @Input()
  set documentCounts(counts: SelectionDataItem[]) {
    if (counts) {
      this.selectionModel.documentCounts = counts
    }
  }

  @Input()
  shortcutKey: string

  @Input()
  extraButtonTitle: string

  creating: boolean = false

  @Output()
  apply = new EventEmitter<ChangedItems>()

  @Output()
  opened = new EventEmitter()

  @Output()
  extraButton = new EventEmitter<ChangedItems>()

  get modifierToggleEnabled(): boolean {
    return this.manyToOne
      ? this.selectionModel.selectionSize() > 1 &&
          this.selectionModel.getExcludedItems().length == 0
      : true
  }

  get name(): string {
    return this.title ? this.title.replace(/\s/g, '_').toLowerCase() : null
  }

  modelIsDirty: boolean = false

  private keyboardIndex: number

  public get scrollViewportHeight(): number {
    const filteredLength = this.filterPipe.transform(
      this.items,
      this.filterText
    ).length
    return Math.min(filteredLength * this.FILTERABLE_BUTTON_HEIGHT_PX, 400)
  }

  constructor() {
    super()
    this.selectionModelChange.subscribe((updatedModel) => {
      this.modelIsDirty = updatedModel.isDirty()
    })
  }

  ngOnInit(): void {
    if (this.shortcutKey) {
      this.hotkeyService
        .addShortcut({
          keys: this.shortcutKey,
          description: $localize`Open ${this.title} filter`,
        })
        .pipe(
          takeUntil(this.unsubscribeNotifier),
          filter(() => !this.disabled)
        )
        .subscribe(() => {
          this.dropdown.open()
        })
    }
  }

  public trackByItem(index: number, item: MatchingModel) {
    return item?.id ?? index
  }

  applyClicked() {
    if (this.selectionModel.isDirty()) {
      this.dropdown.close()
      if (!this.applyOnClose) {
        this.apply.emit(this.selectionModel.diff())
      }
    }
  }

  createClicked() {
    this.creating = true
    this.createRef(this.filterText)
  }

  dropdownOpenChange(open: boolean): void {
    if (open) {
      setTimeout(() => {
        this.listFilterTextInput?.nativeElement.focus()
        this.buttonsViewport?.checkViewportSize()
      }, 0)
      if (this.editing) {
        this.selectionModel.reset()
        this.modelIsDirty = false
      }
      this.selectionModel.singleSelect =
        this.editing && !this.selectionModel.manyToOne
      this.opened.next(this)
    } else {
      if (this.creating) {
        this.dropdown?.open()
        this.creating = false
      } else {
        this.filterText = ''
        if (this.applyOnClose && this.selectionModel.isDirty()) {
          this.apply.emit(this.selectionModel.diff())
        }
      }
    }
  }

  listFilterEnter(): void {
    let filtered = this.filterPipe.transform(this.items, this.filterText)
    if (filtered.length == 1) {
      this.selectionModel.toggle(filtered[0].id)
      setTimeout(() => {
        if (this.editing) {
          this.applyClicked()
        } else {
          this.dropdown.close()
        }
      }, 200)
    } else if (filtered.length == 0 && this.createRef) {
      this.createClicked()
    }
  }

  excludeClicked(itemID: number) {
    if (this.editing) {
      this.selectionModel.toggle(itemID)
    } else {
      this.selectionModel.exclude(itemID)
    }
  }

  reset() {
    this.selectionModel.reset(true)
    this.selectionModelChange.emit(this.selectionModel)
  }

  getUpdatedDocumentCount(id: number) {
    return this.selectionModel.getDocumentCount(id)
  }

  listKeyDown(event: KeyboardEvent) {
    switch (event.key) {
      case 'ArrowDown':
        if (event.target instanceof HTMLInputElement) {
          if (
            !this.filterText ||
            event.target.selectionStart === this.filterText.length
          ) {
            this.keyboardIndex = -1
            this.focusNextButtonItem()
            event.preventDefault()
          }
        } else if (event.target instanceof HTMLButtonElement) {
          this.syncKeyboardIndexFromButton(event.target)
          this.focusNextButtonItem()
          event.preventDefault()
        }
        break
      case 'ArrowUp':
        if (event.target instanceof HTMLButtonElement) {
          this.syncKeyboardIndexFromButton(event.target)
          if (this.keyboardIndex === 0) {
            this.listFilterTextInput.nativeElement.focus()
          } else {
            this.focusPreviousButtonItem()
          }
          event.preventDefault()
        }
        break
      case 'Tab':
        // just track the index in case user uses arrows
        if (event.target instanceof HTMLInputElement) {
          this.keyboardIndex = 0
        } else if (event.target instanceof HTMLButtonElement) {
          if (event.shiftKey) {
            if (this.keyboardIndex > 0) {
              this.focusPreviousButtonItem(false)
            }
          } else {
            this.focusNextButtonItem(false)
          }
        }
      default:
        break
    }
  }

  focusNextButtonItem(setFocus: boolean = true) {
    this.keyboardIndex = Math.min(this.items.length - 1, this.keyboardIndex + 1)
    if (setFocus) this.setButtonItemFocus()
  }

  focusPreviousButtonItem(setFocus: boolean = true) {
    this.keyboardIndex = Math.max(0, this.keyboardIndex - 1)
    if (setFocus) this.setButtonItemFocus()
  }

  private syncKeyboardIndexFromButton(button: HTMLButtonElement) {
    // because of virtual scrolling, re-calculate the index
    const idx = this.renderedButtons.indexOf(button)
    if (idx >= 0) {
      this.keyboardIndex = this.buttonsViewport.getRenderedRange().start + idx
    }
  }

  setButtonItemFocus() {
    const offset =
      this.keyboardIndex - this.buttonsViewport.getRenderedRange().start
    this.renderedButtons[offset]?.focus()
  }

  hideCount(item: ObjectWithPermissions) {
    // counts are pointless when clicking item would add to the set of docs
    return (
      this.selectionModel.logicalOperator === LogicalOperator.Or &&
      this.manyToOne &&
      this.selectionModel.get(item.id) !== ToggleableItemState.Selected
    )
  }

  extraButtonClicked() {
    // don't apply changes when clicking the extra button
    const applyOnClose = this.applyOnClose
    this.applyOnClose = false
    this.dropdown.close()
    this.extraButton.emit(this.selectionModel.diff())
    this.applyOnClose = applyOnClose
  }
}
