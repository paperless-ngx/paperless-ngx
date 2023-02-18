import {
  Component,
  EventEmitter,
  Input,
  Output,
  ElementRef,
  ViewChild,
} from '@angular/core'
import { FilterPipe } from 'src/app/pipes/filter.pipe'
import { NgbDropdown } from '@ng-bootstrap/ng-bootstrap'
import { ToggleableItemState } from './toggleable-dropdown-button/toggleable-dropdown-button.component'
import { MatchingModel } from 'src/app/data/matching-model'
import { Subject } from 'rxjs'

export interface ChangedItems {
  itemsToAdd: MatchingModel[]
  itemsToRemove: MatchingModel[]
}

export class FilterableDropdownSelectionModel {
  changed = new Subject<FilterableDropdownSelectionModel>()

  multiple = false
  private _logicalOperator = 'and'
  temporaryLogicalOperator = this._logicalOperator

  items: MatchingModel[] = []

  get itemsSorted(): MatchingModel[] {
    // TODO: this is getting called very often
    return this.items.sort((a, b) => {
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
      state == null ||
      (state != ToggleableItemState.Selected &&
        state != ToggleableItemState.Excluded)
    ) {
      this.temporarySelectionStates.set(id, ToggleableItemState.Selected)
    } else if (
      state == ToggleableItemState.Selected ||
      state == ToggleableItemState.Excluded
    ) {
      this.temporarySelectionStates.delete(id)
    }

    if (!this.multiple) {
      for (let key of this.temporarySelectionStates.keys()) {
        if (key != id) {
          this.temporarySelectionStates.delete(key)
        }
      }
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
    if (state == null || state != ToggleableItemState.Excluded) {
      this.temporarySelectionStates.set(id, ToggleableItemState.Excluded)
      this.temporaryLogicalOperator = this._logicalOperator = 'and'
    } else if (state == ToggleableItemState.Excluded) {
      this.temporarySelectionStates.delete(id)
    }

    if (!this.multiple) {
      for (let key of this.temporarySelectionStates.keys()) {
        if (key != id) {
          this.temporarySelectionStates.delete(key)
        }
      }
    }

    if (fireEvent) {
      this.changed.next(this)
    }
  }

  private getNonTemporary(id: number) {
    return this.selectionStates.get(id) || ToggleableItemState.NotSelected
  }

  get logicalOperator(): string {
    return this.temporaryLogicalOperator
  }

  set logicalOperator(operator: string) {
    this.temporaryLogicalOperator = operator
  }

  toggleOperator() {
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
    this.temporaryLogicalOperator = this._logicalOperator = 'and'
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

  init(map) {
    this.temporarySelectionStates = map
    this.apply()
  }

  apply() {
    this.selectionStates.clear()
    this.temporarySelectionStates.forEach((value, key) => {
      this.selectionStates.set(key, value)
    })
    this._logicalOperator = this.temporaryLogicalOperator
  }

  reset() {
    this.temporarySelectionStates.clear()
    this.selectionStates.forEach((value, key) => {
      this.temporarySelectionStates.set(key, value)
    })
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
  selector: 'app-filterable-dropdown',
  templateUrl: './filterable-dropdown.component.html',
  styleUrls: ['./filterable-dropdown.component.scss'],
})
export class FilterableDropdownComponent {
  @ViewChild('listFilterTextInput') listFilterTextInput: ElementRef
  @ViewChild('dropdown') dropdown: NgbDropdown

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

  _selectionModel = new FilterableDropdownSelectionModel()

  @Input()
  set selectionModel(model: FilterableDropdownSelectionModel) {
    if (this.selectionModel) {
      this.selectionModel.changed.complete()
      model.items = this.selectionModel.items
      model.multiple = this.selectionModel.multiple
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
  set multiple(value: boolean) {
    this.selectionModel.multiple = value
  }

  get multiple() {
    return this.selectionModel.multiple
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

  @Output()
  apply = new EventEmitter<ChangedItems>()

  @Output()
  opened = new EventEmitter()

  get operatorToggleEnabled(): boolean {
    return (
      this.selectionModel.selectionSize() > 1 &&
      this.selectionModel.getExcludedItems().length == 0
    )
  }

  modelIsDirty: boolean = false

  constructor(private filterPipe: FilterPipe) {
    this.selectionModel = new FilterableDropdownSelectionModel()
    this.selectionModelChange.subscribe((updatedModel) => {
      this.modelIsDirty = updatedModel.isDirty()
    })
  }

  applyClicked() {
    if (this.selectionModel.isDirty()) {
      this.dropdown.close()
      if (!this.applyOnClose) {
        this.apply.emit(this.selectionModel.diff())
      }
    }
  }

  dropdownOpenChange(open: boolean): void {
    if (open) {
      setTimeout(() => {
        this.listFilterTextInput.nativeElement.focus()
      }, 0)
      if (this.editing) {
        this.selectionModel.reset()
        this.modelIsDirty = false
      }
      this.opened.next(this)
    } else {
      this.filterText = ''
      if (this.applyOnClose && this.selectionModel.isDirty()) {
        this.apply.emit(this.selectionModel.diff())
      }
    }
  }

  listFilterEnter(): void {
    let filtered = this.filterPipe.transform(this.items, this.filterText)
    if (filtered.length == 1) {
      this.selectionModel.toggle(filtered[0].id)
      if (this.editing) {
        this.applyClicked()
      } else {
        this.dropdown.close()
      }
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
    this.selectionModel.reset()
    this.selectionModelChange.emit(this.selectionModel)
  }
}
