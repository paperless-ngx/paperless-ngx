import { Component, EventEmitter, Input, Output, ElementRef, ViewChild, OnChanges, SimpleChange } from '@angular/core';
import { FilterRule } from 'src/app/data/filter-rule';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { NgbDate, NgbDateStruct, NgbDatepicker } from '@ng-bootstrap/ng-bootstrap';

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

  @ViewChild('dpAfter') dpAfter: NgbDatepicker
  @ViewChild('dpBefore') dpBefore: NgbDatepicker

  _dateBefore: NgbDateStruct
  _dateAfter: NgbDateStruct

  get _maxDate(): NgbDate {
    let date = new Date()
    return NgbDate.from({year: date.getFullYear(), month: date.getMonth() + 1, day: date.getDate()})
  }

  ngOnChanges(changes: SimpleChange) {
    // this is a hacky workaround perhaps because of https://github.com/angular/angular/issues/11097
    let dateString: string
    let dateAfterChange: SimpleChange = changes['dateAfter']
    let dateBeforeChange: SimpleChange = changes['dateBefore']

    if (dateAfterChange && dateAfterChange.currentValue && this.dpAfter) {
      let dateAfterDate = dateAfterChange.currentValue as NgbDateStruct
      let dpAfterElRef: ElementRef = this.dpAfter['_elRef']
      dateString = `${dateAfterDate.year}-${dateAfterDate.month.toString().padStart(2,'0')}-${dateAfterDate.day.toString().padStart(2,'0')}`
      dpAfterElRef.nativeElement.value = dateString
    } else if (dateBeforeChange && dateBeforeChange.currentValue && this.dpBefore) {
      let dateBeforeDate = dateBeforeChange.currentValue as NgbDateStruct
      let dpBeforeElRef: ElementRef = this.dpBefore['_elRef']
      dateString = `${dateBeforeChange.currentValue.year}-${dateBeforeChange.currentValue.month.toString().padStart(2,'0')}-${dateBeforeChange.currentValue.day.toString().padStart(2,'0')}`
      dpBeforeElRef.nativeElement.value = dateString
    }
  }

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
