import { Component, EventEmitter, Input, Output, ElementRef, ViewChild, SimpleChange } from '@angular/core';
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

  isStringRange(range: any) {
    return typeof range == 'string'
  }

  ngOnChanges(changes: SimpleChange) {
    // this is a hacky workaround perhaps because of https://github.com/angular/angular/issues/11097
    let dateString: string = ''
    let dateAfterChange: SimpleChange
    let dateBeforeChange: SimpleChange
    if (changes) {
      dateAfterChange = changes['dateAfter']
      dateBeforeChange = changes['dateBefore']
    }

    if (this.dpBefore && this.dpAfter) {
      let dpAfterElRef: ElementRef = this.dpAfter['_elRef']
      let dpBeforeElRef: ElementRef = this.dpBefore['_elRef']

      if (dateAfterChange && dateAfterChange.currentValue) {
        let dateAfterDate = dateAfterChange.currentValue as NgbDateStruct
        dateString = `${dateAfterDate.year}-${dateAfterDate.month.toString().padStart(2,'0')}-${dateAfterDate.day.toString().padStart(2,'0')}`
        dpAfterElRef.nativeElement.value = dateString
      } else if (dateBeforeChange && dateBeforeChange.currentValue) {
        let dateBeforeDate = dateBeforeChange.currentValue as NgbDateStruct
        dateString = `${dateBeforeDate.year}-${dateBeforeDate.month.toString().padStart(2,'0')}-${dateBeforeDate.day.toString().padStart(2,'0')}`
        dpBeforeElRef.nativeElement.value = dateString
      } else {
        dpAfterElRef.nativeElement.value = dateString
        dpBeforeElRef.nativeElement.value = dateString
      }
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

  clearAfter() {
    this.dateAfterSet.next()
  }

  clearBefore() {
    this.dateBeforeSet.next()
  }
}
