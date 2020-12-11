import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FilterRuleType, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { ObjectWithId } from 'src/app/data/object-with-id';

@Component({
  selector: 'app-filter-dropdown',
  templateUrl: './filter-dropdown.component.html',
  styleUrls: ['./filter-dropdown.component.scss']
})
export class FilterDropdownComponent implements OnInit {

  constructor() { }

  @Input()
  filterRuleTypeID: number

  @Output()
  toggle = new EventEmitter()

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

  toggleItem(item: ObjectWithId) {
    this.toggle.emit(item)
  }
}
