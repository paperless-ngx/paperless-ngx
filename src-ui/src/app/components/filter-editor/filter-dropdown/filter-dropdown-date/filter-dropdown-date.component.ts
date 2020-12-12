import { Component, EventEmitter, Input, OnInit, Output, ElementRef, ViewChild } from '@angular/core';
import { FilterRule } from 'src/app/data/filter-rule';
import { FilterRuleType, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { FilterDropdownComponent } from '../filter-dropdown.component'
import { NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-filter-dropdown-date',
  templateUrl: './filter-dropdown-date.component.html',
  styleUrls: ['./filter-dropdown-date.component.scss']
})
export class FilterDropdownDateComponent extends FilterDropdownComponent {

  @Input()
  filterRuleTypeIDs: number[] = []

  @Output()
  selected = new EventEmitter()

  filterRuleTypes: FilterRuleType[] = []
  dateAfter: NgbDateStruct
  dateBefore: NgbDateStruct

  ngOnInit(): void {
    this.filterRuleTypes = this.filterRuleTypeIDs.map(id => FILTER_RULE_TYPES.find(rt => rt.id == id))
    this.filterRuleTypeID = this.filterRuleTypeIDs[0]
    super.ngOnInit()
  }

  setDateQuickFilter(range: any) {
    this.dateAfter = this.dateBefore = undefined
    let now = new Date()
    switch (typeof range) {
      case 'number':
        now.setDate(now.getDate() - range)
        this.dateAfter = { year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() }
        this.dateSelected(this.dateAfter)
        break;

      case 'string':
        let date = { year: now.getFullYear(), month: now.getMonth() + 1, day: 1 }
        if (range == 'year') date.month = 1
        this.dateAfter = date
        this.dateSelected(this.dateAfter)
        break;

      default:
        break;
    }
  }

  dateSelected(date:NgbDateStruct) {
    let isAfter = this.dateAfter !== undefined
    let filterRuleType = this.filterRuleTypes.find(rt => rt.filtervar.indexOf(isAfter ? 'gt' : 'lt') > -1)
    if (filterRuleType) {
      let dateFilterRule:FilterRule = {value: `${date.year}-${date.month}-${date.day}`, type: filterRuleType}
      this.selected.emit(dateFilterRule)
    }
  }
}
