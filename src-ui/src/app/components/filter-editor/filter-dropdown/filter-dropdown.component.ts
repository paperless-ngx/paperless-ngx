import { Component, EventEmitter, Input, OnInit, Output, ElementRef, ViewChild } from '@angular/core';
import { FilterRuleType, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { FilterPipe } from  'src/app/pipes/filter.pipe';

@Component({
  selector: 'app-filter-dropdown',
  templateUrl: './filter-dropdown.component.html',
  styleUrls: ['./filter-dropdown.component.scss']
})
export class FilterDropdownComponent implements OnInit {

  constructor(private filterPipe: FilterPipe) { }

  @Input()
  filterRuleTypeID: number

  @Output()
  toggle = new EventEmitter()

  @ViewChild('listFilterTextInput') listFilterTextInput: ElementRef

  items: ObjectWithId[] = []
  itemsActive: ObjectWithId[] = []
  title: string
  filterText: string
  display: string

  ngOnInit(): void {
    let filterRuleType: FilterRuleType = FILTER_RULE_TYPES.find(t => t.id == this.filterRuleTypeID)
    this.title = filterRuleType.displayName
    this.display = filterRuleType.datatype
  }

  toggleItem(item: ObjectWithId): void {
    this.toggle.emit(item)
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
  }
}
