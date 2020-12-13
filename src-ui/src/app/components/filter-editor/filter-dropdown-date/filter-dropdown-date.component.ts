import { Component, EventEmitter, Input, Output, ElementRef, ViewChild } from '@angular/core';
import { FilterRule } from 'src/app/data/filter-rule';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { NgbDate, NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-filter-dropdown-date',
  templateUrl: './filter-dropdown-date.component.html',
  styleUrls: ['./filter-dropdown-date.component.scss']
})
export class FilterDropdownDateComponent {

  @Input()
  dateBefore: NgbDateStruct

  @Input()
  dateAfter: NgbDateStruct

  @Input()
  title: string

  @Output()
  dateBeforeSet = new EventEmitter()

  @Output()
  dateAfterSet = new EventEmitter()

  _dateBefore: NgbDateStruct
  _dateAfter: NgbDateStruct

  setDateQuickFilter(range: any) {
    this._dateAfter = this._dateBefore = undefined
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
    this._dateAfter = newDate
    this.onDateSelected(this._dateAfter)
  }

  onDateSelected(date:NgbDateStruct) {
    let emitter = this._dateAfter && NgbDate.from(this._dateAfter).equals(date) ? this.dateAfterSet : this.dateBeforeSet
    emitter.emit(date)
  }
}
