import { Component, EventEmitter, Input, Output, ElementRef, ViewChild } from '@angular/core';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { FilterPipe } from  'src/app/pipes/filter.pipe';
import { NgbDropdown } from '@ng-bootstrap/ng-bootstrap'

export interface SelectableItem {
  item: PaperlessTag | PaperlessDocumentType | PaperlessCorrespondent,
  state: SelectableItemState
}

export enum SelectableItemState {
  NotSelected = 0,
  Selected = 1,
  PartiallySelected = 2
}

export enum FilterableDropdownType {
  Filtering = 'filtering',
  Editing = 'editing'
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
  set items(items: ObjectWithId[]) {
    if (items) {
      this._selectableItems = items.map(i => {
        return {item: i, state: SelectableItemState.NotSelected}
      })
    }
  }

  _selectableItems: SelectableItem[] = []

  @Input()
  set selectableItems (selectableItems: SelectableItem[]) {
    if (this.type == FilterableDropdownType.Editing && this.dropdown?.isOpen()) return
    else this._selectableItems = selectableItems
  }

  get selectableItems(): SelectableItem[] {
    return this._selectableItems
  }

  @Input()
  set itemsSelected(itemsSelected: ObjectWithId[]) {
    this.selectableItems.forEach(i => {
      i.state = (itemsSelected.find(is => is.id == i.item.id)) ? SelectableItemState.Selected : SelectableItemState.NotSelected
    })
  }

  get itemsSelected() :ObjectWithId[] {
    return this.selectableItems.filter(si => si.state == SelectableItemState.Selected).map(si => si.item)
  }

  @Input()
  title: string

  @Input()
  icon: string

  @Input()
  type: FilterableDropdownType = FilterableDropdownType.Filtering

  types = FilterableDropdownType

  @Input()
  singular: boolean = false

  @Output()
  toggle = new EventEmitter()

  @Output()
  open = new EventEmitter()

  @Output()
  editingComplete = new EventEmitter()

  constructor(private filterPipe: FilterPipe) { }

  toggleItem(selectableItem: SelectableItem): void {
    if (this.singular && selectableItem.state == SelectableItemState.Selected) {
      this._selectableItems.filter(si => si.item.id !== selectableItem.item.id).forEach(si => si.state = SelectableItemState.NotSelected)
    }
    this.toggle.emit(selectableItem.item)
  }

  dropdownOpenChange(open: boolean): void {
    if (open) {
      setTimeout(() => {
        this.listFilterTextInput.nativeElement.focus();
      }, 0)
      this.open.next()
    } else {
      this.filterText = ''
      if (this.type == FilterableDropdownType.Editing) this.editingComplete.emit(this.itemsSelected)
    }
  }

  listFilterEnter(): void {
    let filtered = this.filterPipe.transform(this.selectableItems, this.filterText)
    if (filtered.length == 1) this.toggleItem(filtered.shift())
    this.dropdown.close()
  }
}
