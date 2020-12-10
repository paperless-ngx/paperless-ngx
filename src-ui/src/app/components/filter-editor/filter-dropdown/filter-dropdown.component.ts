import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FilterRuleType, FILTER_CORRESPONDENT, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_TITLE, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { MatchingModel } from 'src/app/data/matching-model';

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

  items: MatchingModel[] = []
  itemsActive: MatchingModel[] = []
  title: string
  filterText: string

  ngOnInit(): void {
    let filterRuleType: FilterRuleType = FILTER_RULE_TYPES.find(t => t.id == this.filterRuleTypeID)
    this.title = filterRuleType.name
  }

  toggleItem(item: ObjectWithId) {
    this.toggle.emit(item, this.filterRuleTypeID)
  }
}
