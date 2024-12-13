import {
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnInit,
  Output,
  ViewChild,
} from '@angular/core'
import { NgbDropdown } from '@ng-bootstrap/ng-bootstrap'
import { Subject, filter, takeUntil } from 'rxjs'
import { MatchingModel } from 'src/app/data/matching-model'
import { ObjectWithPermissions } from 'src/app/data/object-with-permissions'
import { FilterPipe } from 'src/app/pipes/filter.pipe'
import { HotKeyService } from 'src/app/services/hot-key.service'
import { SelectionDataItem } from 'src/app/services/rest/document.service'
import { popperOptionsReenablePreventOverflow } from 'src/app/utils/popper-options'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
import { ToggleableItemState } from './toggleable-dropdown-button/toggleable-dropdown-button.component'

export interface ChangedItems {
  itemsToAdd: MatchingModel[]
  itemsToRemove: MatchingModel[]
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
  public set documentCounts(counts: SelectionDataItem[]) {
    this._documentCounts = counts
  }

  private _items: MatchingModel[] = []
  get items(): MatchingModel[] {
    return this._items
  }

  set items(items: MatchingModel[]) {
    this._items = items
    this.sortItems()
  }

  private sortItems() {
    this._items.sort((a, b) => {
      if (a.id == null && b.id != null) {
        return -1
      } else if (a.id != null && b.id == null) {
        return 1
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
        this.getDocumentCount(a.id) > this.getDocumentCount(b.id)
      ) {
        return -1
      } else if (
        this._documentCounts.length &&
        this.getDocumentCount(a.id) < this.getDocumentCount(b.id)
      ) {
        return 1
      } else {
        return a.name.localeCompare(b.name)
      }
    })
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
  }

  toggleOperator() {
    this.changed.next(this)
  }

  get intersection(): Intersection {
    return this.temporaryIntersection
  }

  set intersection(intersection: Intersection) {
    this.temporaryIntersection = intersection
  }

  toggleIntersection() {
    if (this.temporarySelectionStates.size === 0) return
    let newState =
      this.intersection == Intersection.Include
        ? ToggleableItemState.Selected
        : ToggleableItemState.Excluded
    this.temporarySelectionStates.forEach((state, key) => {
      this.temporarySelectionStates.set(key, newState)
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
      this.selectionSize() == 1 &&
      this.get(null) == ToggleableItemState.Selected
    )
  }

  getDocumentCount(id: number) {
    return this._documentCounts.find((c) => c.id === id)?.document_count
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
})
export class FilterableDropdownComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  @ViewChild('listFilterTextInput') listFilterTextInput: ElementRef
  @ViewChild('dropdown') dropdown: NgbDropdown
  @ViewChild('buttonItems') buttonItems: ElementRef

  public popperOptions = popperOptionsReenablePreventOverflow

  filterText: string

  @Input()
  set items(items: MatchingModel[]) {
    if (items) {
      this._selectionModel.items = Array.from(items)
      this._selectionModel.items.unshift({
        name: $localize`:Filter drop down element to filter for documents with no correspondent/type/tag assigned:Not assigned`,
        id: null,
      })
    }
  }

  get items(): MatchingModel[] {
    return this._selectionModel.items
  }

  _selectionModel: FilterableDropdownSelectionModel =
    new FilterableDropdownSelectionModel()

  @Input()
  set selectionModel(model: FilterableDropdownSelectionModel) {
    if (this.selectionModel) {
      this.selectionModel.changed.complete()
      model.items = this.selectionModel.items
      model.manyToOne = this.selectionModel.manyToOne
      model.singleSelect = this.editing && !this.selectionModel.manyToOne
    }
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

  @Input()
  set manyToOne(manyToOne: boolean) {
    this.selectionModel.manyToOne = manyToOne
  }

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

  @Input()
  editing = false

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
      : !this.selectionModel.isNoneSelected()
  }

  get name(): string {
    return this.title ? this.title.replace(/\s/g, '_').toLowerCase() : null
  }

  modelIsDirty: boolean = false

  private keyboardIndex: number

  constructor(
    private filterPipe: FilterPipe,
    private hotkeyService: HotKeyService
  ) {
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
      }, 0)
      if (this.editing) {
        this.selectionModel.reset()
        this.modelIsDirty = false
      }
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
          this.focusNextButtonItem()
          event.preventDefault()
        }
        break
      case 'ArrowUp':
        if (event.target instanceof HTMLButtonElement) {
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

  setButtonItemFocus() {
    this.buttonItems.nativeElement.children[
      this.keyboardIndex
    ]?.children[0].focus()
  }

  setButtonItemIndex(index: number) {
    // just track the index in case user uses arrows
    this.keyboardIndex = index
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
