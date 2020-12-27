import { Component, EventEmitter, Input, Output, ElementRef, ViewChild } from '@angular/core';
import { FilterPipe } from  'src/app/pipes/filter.pipe';
import { NgbDropdown } from '@ng-bootstrap/ng-bootstrap'
import { ToggleableItem, ToggleableItemState } from './toggleable-dropdown-button/toggleable-dropdown-button.component';
import { MatchingModel } from 'src/app/data/matching-model';
import { Subject } from 'rxjs';
import { ThrowStmt } from '@angular/compiler';

export enum FilterableDropdownType {
  Filtering = 'filtering',
  Editing = 'editing'
}

export class FilterableDropdownSelectionModel {

  changed = new Subject<FilterableDropdownSelectionModel>()

  multiple = false

  items: MatchingModel[] = []

  selection = new Map<number, ToggleableItemState>()

  getSelectedItems() {
    return this.items.filter(i => this.selection.get(i.id) == ToggleableItemState.Selected)
  }

  set(id: number, state: ToggleableItemState, fireEvent = true) {
    this.selection.set(id, state)
    if (fireEvent) {
      this.changed.next(this)
    }
  }

  toggle(id: number, fireEvent = true) {
    let state = this.selection.get(id)
    if (state == null || state != ToggleableItemState.Selected) {
      this.selection.set(id, ToggleableItemState.Selected)
    } else if (state == ToggleableItemState.Selected) {
      this.selection.set(id, ToggleableItemState.NotSelected)
    }

    if (!this.multiple) {
      for (let key of this.selection.keys()) {
        if (key != id) {
          this.selection.set(key, ToggleableItemState.NotSelected)
        }
      }
    }

    if (fireEvent) {
      this.changed.next(this)
    }
    
  }

  get(id: number) {
    return this.selection.get(id) || ToggleableItemState.NotSelected
  }

  selectionSize() {
    return this.getSelectedItems().length
  }

  clear(fireEvent = true) {
    this.selection.clear()
    if (fireEvent) {
      this.changed.next(this)
    }
  }
}

@Component({
  selector: 'app-filterable-dropdown',
  templateUrl: './filterable-dropdown.component.html',
  styleUrls: ['./filterable-dropdown.component.scss']
})
export class FilterableDropdownComponent {

  @ViewChild('listFilterTextInput') listFilterTextInput: ElementRef
  @ViewChild('dropdown') dropdown: NgbDropdown

  filterText: string

  @Input()
  set items(items: MatchingModel[]) {
    if (items) {
      this._selectionModel.items = items
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
    model.changed.subscribe(updatedModel => {
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
  icon: string

  @Input()
  type: FilterableDropdownType = FilterableDropdownType.Filtering

  types = FilterableDropdownType

  hasBeenToggled:boolean = false

  constructor(private filterPipe: FilterPipe) {
    this.selectionModel = new FilterableDropdownSelectionModel()
  }

  toggleItem(toggleableItem: ToggleableItem): void {
    // if (this.singular && toggleableItem.state == ToggleableItemState.Selected) {
    //   this.selectionModel.items.filter(ti => ti.item.id !== toggleableItem.item.id).forEach(ti => ti.state = ToggleableItemState.NotSelected)
    // }
    // this.hasBeenToggled = true
    // this.toggle.emit(toggleableItem.item)
  }

  dropdownOpenChange(open: boolean): void {
    // if (open) {
    //   setTimeout(() => {
    //     this.listFilterTextInput.nativeElement.focus();
    //   }, 0)
    //   this.hasBeenToggled = false
    //   this.open.next()
    // } else {
    //   this.filterText = ''
    //   if (this.type == FilterableDropdownType.Editing) this.editingComplete.emit(this.toggleableItems)
    // }
  }

  listFilterEnter(): void {
    // let filtered = this.filterPipe.transform(this.toggleableItems, this.filterText)
    // if (filtered.length == 1) {
    //   let toggleableItem = this.toggleableItems.find(ti => ti.item.id == filtered[0].item.id)
    //   if (toggleableItem) toggleableItem.state = ToggleableItemState.Selected
    //   this.toggleItem(filtered[0])
    //   this.dropdown.close()
    // }
  }
}
