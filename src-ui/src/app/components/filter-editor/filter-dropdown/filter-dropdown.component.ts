import { Component, EventEmitter, Input, Output, ElementRef, ViewChild } from '@angular/core';
import { Observable } from 'rxjs';
import { Results } from 'src/app/data/results';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { FilterPipe } from  'src/app/pipes/filter.pipe';
import { NgbDropdown } from '@ng-bootstrap/ng-bootstrap'

@Component({
  selector: 'app-filter-dropdown',
  templateUrl: './filter-dropdown.component.html',
  styleUrls: ['./filter-dropdown.component.scss']
})
export class FilterDropdownComponent {

  constructor(private filterPipe: FilterPipe) { }

  @Input()
  items: ObjectWithId[]

  @Input()
  itemsSelected: ObjectWithId[]

  @Input()
  title: string

  @Input()
  display: string

  @Output()
  toggle = new EventEmitter()

  @ViewChild('listFilterTextInput') listFilterTextInput: ElementRef
  @ViewChild('filterDropdown') filterDropdown: NgbDropdown

  filterText: string

  toggleItem(item: ObjectWithId): void {
    this.toggle.emit(item)
  }

  isItemSelected(item: ObjectWithId): boolean {
    return this.itemsSelected?.find(i => i.id == item.id) !== undefined
  }

  dropdownOpenChange(open: boolean): void {
    if (open) {
      setTimeout(() => {
        this.listFilterTextInput.nativeElement.focus();
      }, 0);
    } else {
      this.filterText = ''
    }
  }

  listFilterEnter(): void {
    let filtered = this.filterPipe.transform(this.items, this.filterText)
    if (filtered.length == 1) this.toggleItem(filtered.shift())
    this.filterDropdown.close()
  }
}
