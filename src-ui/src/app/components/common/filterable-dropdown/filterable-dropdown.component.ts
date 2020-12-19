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

@Component({
  selector: 'app-filterable-dropdown',
  templateUrl: './filterable-dropdown.component.html',
  styleUrls: ['./filterable-dropdown.component.scss']
})
export class FilterableDropdownComponent {

  constructor(private filterPipe: FilterPipe) { }

  @Input()
  set items(items: ObjectWithId[]) {
    if (items) {
      this.selectableItems = items.map(i => {
        return {item: i, state: SelectableItemState.NotSelected}
      })
    }
  }

  selectableItems: SelectableItem[] = []

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

  @Output()
  toggle = new EventEmitter()

  @Output()
  close = new EventEmitter()

  @ViewChild('listFilterTextInput') listFilterTextInput: ElementRef
  @ViewChild('dropdown') dropdown: NgbDropdown

  filterText: string

  toggleItem(selectableItem: SelectableItem): void {
    this.toggle.emit(selectableItem.item)
  }

  dropdownOpenChange(open: boolean): void {
    if (open) {
      setTimeout(() => {
        this.listFilterTextInput.nativeElement.focus();
      }, 0);
    } else {
      this.filterText = ''
      this.close.next()
    }
  }

  listFilterEnter(): void {
    let filtered = this.filterPipe.transform(this.selectableItems, this.filterText)
    if (filtered.length == 1) this.toggleItem(filtered.shift())
    this.dropdown.close()
  }
}
