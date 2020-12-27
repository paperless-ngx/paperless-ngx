import { Component, EventEmitter, Input, Output, ElementRef, ViewChild } from '@angular/core';
import { FilterPipe } from  'src/app/pipes/filter.pipe';
import { NgbDropdown } from '@ng-bootstrap/ng-bootstrap'
import { ToggleableItem, ToggleableItemState } from './toggleable-dropdown-button/toggleable-dropdown-button.component';
import { MatchingModel } from 'src/app/data/matching-model';
import { Subject } from 'rxjs';

export enum FilterableDropdownType {
  Filtering = 'filtering',
  Editing = 'editing'
}

export class FilterableDropdownSelectionModel {

  changed = new Subject<FilterableDropdownSelectionModel>()

  multiple = false

  items: ToggleableItem[] = []

  getSelected() {
    return this.items.filter(i => i.state == ToggleableItemState.Selected).map(i => i.item)
  }



  toggle(item: MatchingModel, fireEvent = true) {
    console.log("TOGGLE TAG")
    let toggleableItem = this.items.find(i => i.item == item)
    console.log(toggleableItem)

    if (toggleableItem) {
      if (toggleableItem.state == ToggleableItemState.Selected) {
        toggleableItem.state = ToggleableItemState.NotSelected
      } else {
        this.items.forEach(i => {
          if (i.item == item) {
            i.state = ToggleableItemState.Selected
          } else if (!this.multiple) {
            i.state = ToggleableItemState.NotSelected
          }
        })
      }
      if (fireEvent) {
        this.changed.next(this)
      }
    }
  }

  selectionSize() {
    return this.getSelected().length
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
      this._selectionModel.items = items.map(i => {
        return {item: i, state: ToggleableItemState.NotSelected, count: i.document_count}
      })
    }
  }

  get items(): MatchingModel[] {
    return this._selectionModel.items.map(i => i.item)
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
