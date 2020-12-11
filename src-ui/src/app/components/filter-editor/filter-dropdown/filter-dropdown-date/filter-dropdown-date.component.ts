import { Component, EventEmitter, Input, OnInit, Output, ElementRef, ViewChild } from '@angular/core';
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
  showYear: boolean = false
  showMonth: boolean = false
  dateAfter: NgbDateStruct
  dateBefore: NgbDateStruct

  ngOnInit(): void {
    this.filterRuleTypes = this.filterRuleTypeIDs.map(id => FILTER_RULE_TYPES.find(rt => rt.id == id))
    this.filterRuleTypeID = this.filterRuleTypeIDs[0]
    super.ngOnInit()

    this.showYear = this.filterRuleTypes.find(rt => rt.filtervar.indexOf('year') > -1) !== undefined
    this.showMonth = this.filterRuleTypes.find(rt => rt.filtervar.indexOf('month') > -1) !== undefined
  }

  setQuickFilter(range: any) {
    this.dateAfter = this.dateBefore = undefined
    switch (typeof range) {
      case 'number':
        let date = new Date();
        date.setDate(date.getDate() - range)
        this.dateAfter = { year: date.getFullYear(), month: date.getMonth() + 1, day: date.getDate() }
        break;

      case 'string':
        let filterRuleType = this.filterRuleTypes.find(rt => rt.filtervar.indexOf(range) > -1)
        console.log(range);
        break;

      default:
        break;
    }
  }
}
