import { Component, EventEmitter, Input, Output, ElementRef, ViewChild } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { FilterPipe } from  'src/app/pipes/filter.pipe';
import { NgbDropdown } from '@ng-bootstrap/ng-bootstrap'
import { ToggleableItem, ToggleableItemState } from './toggleable-dropdown-button/toggleable-dropdown-button.component';

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
  set items(items: (PaperlessTag | PaperlessCorrespondent | PaperlessDocumentType)[]) {
    if (items) {
      this._toggleableItems = items.map(i => {
        return {item: i, state: ToggleableItemState.NotSelected, count: i.document_count}
      })
    }
  }

  _toggleableItems: ToggleableItem[] = []

  @Input()
  set toggleableItems (toggleableItems: ToggleableItem[]) {
    if (this.type == FilterableDropdownType.Editing && this.dropdown?.isOpen()) return
    else this._toggleableItems = toggleableItems
  }

  get toggleableItems(): ToggleableItem[] {
    return this._toggleableItems
  }

  @Input()
  set itemsSelected(itemsSelected: (PaperlessTag | PaperlessCorrespondent | PaperlessDocumentType)[]) {
    this.toggleableItems.forEach(i => {
      i.state = (itemsSelected.find(is => is.id == i.item.id)) ? ToggleableItemState.Selected : ToggleableItemState.NotSelected
    })
  }

  get itemsSelected() :(PaperlessTag | PaperlessCorrespondent | PaperlessDocumentType)[] {
    return this.toggleableItems.filter(si => si.state == ToggleableItemState.Selected).map(si => si.item)
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

  get showCounts(): boolean {
    return this.type == FilterableDropdownType.Editing || (this.type == FilterableDropdownType.Filtering && this.itemsSelected == 0)
  }

  constructor(private filterPipe: FilterPipe) { }

  toggleItem(toggleableItem: ToggleableItem): void {
    if (this.singular && toggleableItem.state == ToggleableItemState.Selected) {
      this._toggleableItems.filter(si => si.item.id !== toggleableItem.item.id).forEach(si => si.state = ToggleableItemState.NotSelected)
    }
    this.toggle.emit(toggleableItem.item)
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
    let filtered = this.filterPipe.transform(this.toggleableItems, this.filterText)
    if (filtered.length == 1) this.toggleItem(filtered.shift())
    this.dropdown.close()
  }
}
