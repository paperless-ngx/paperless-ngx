import { Component, EventEmitter, Input, OnInit, Output, ElementRef, ViewChild } from '@angular/core';
import { FilterRule } from 'src/app/data/filter-rule';
import { FilterRuleType, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { FilterDropdownComponent } from '../filter-dropdown.component'
import { NgbDate, NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';

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
    let date = new Date()
    let newDate: NgbDateStruct = { year: date.getFullYear(), month: date.getMonth() + 1, day: date.getDate() }
    switch (typeof range) {
      case 'number':
        date.setDate(date.getDate() - range)
        newDate.year = date.getFullYear()
        newDate.month = date.getMonth() + 1
        newDate.day = date.getDate()
        break

      case 'string':
        newDate.day = 1
        if (range == 'year') newDate.month = 1
        break

      default:
        break
    }
    this.dateAfter = newDate
    this.dateSelected(this.dateAfter)
  }

  dateSelected(date:NgbDateStruct) {
    let isAfter = NgbDate.from(this.dateAfter).equals(date)

    let filterRuleType = this.filterRuleTypes.find(rt => rt.filtervar.indexOf(isAfter ? 'gt' : 'lt') > -1)
    if (filterRuleType) {
      let dateFilterRule:FilterRule = {value: `${date.year}-${date.month.toString().padStart(2,'0')}-${date.day.toString().padStart(2,'0')}`, type: filterRuleType}
      this.selected.emit(dateFilterRule)
    }
  }
}
