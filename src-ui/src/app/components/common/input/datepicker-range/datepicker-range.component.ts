import { Component, EventEmitter, inject, Input, OnInit, Output } from '@angular/core'
import { NgbCalendar, NgbDate, NgbDateParserFormatter } from '@ng-bootstrap/ng-bootstrap'
import { FormsModule } from '@angular/forms'
import { JsonPipe } from '@angular/common'
import { AbstractInputComponent } from '../abstract-input'
import { end } from '@popperjs/core'

@Component({
  selector: 'pngx-input-datepicker-range',
  templateUrl: './datepicker-range.component.html',
  styleUrls: ['./datepicker-range.component.scss'],
})
export class DatepickerRangeComponent extends AbstractInputComponent<string>
  implements OnInit {
  calendar = inject(NgbCalendar)
  formatter = inject(NgbDateParserFormatter)
  @Output() dateRangeChange = new EventEmitter<{ fromDate: string | null, toDate: string | null }>()
  @Output() confirmButton = new EventEmitter()

  selectDateRange: number = 1
  hoveredDate: NgbDate | null = null
  fromDate: NgbDate | null = this.calendar.getToday()
  toDate: NgbDate | null = this.calendar.getNext(this.calendar.getToday(), 'd', 10)

  ngOnInit() {
    const today = new Date()
    const tomorrow = new Date()
    tomorrow.setDate(today.getDate() + 1)
    this.fromDate = this.convertDateToNgbDate(today)
    this.toDate = this.convertDateToNgbDate(today)
    this.emitDateRangeChange()
  }

  function

  convertDateToNgbDate(date: Date): NgbDate {
    return new NgbDate(date.getFullYear(), date.getMonth() + 1, date.getDate())
  }

  convertSelectToDate(value) {
    const today = new Date()
    const tomorrow = new Date()
    tomorrow.setDate(today.getDate() + 1)

    if (value == 'today') {
      this.fromDate = this.convertDateToNgbDate(today)
      this.toDate = this.convertDateToNgbDate(today)
    } else if (value == 'week') {
      const startOfWeek = new Date(today)
      startOfWeek.setDate(today.getDate() - today.getDay() + 1)
      this.fromDate = this.convertDateToNgbDate(startOfWeek)
      const endOfWeek = new Date(startOfWeek)
      endOfWeek.setDate(startOfWeek.getDate() + 6)
      this.toDate = this.convertDateToNgbDate(endOfWeek)
    } else if (value == 'month') {
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1)
      const startOfNextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 1)
      const endOfMonth = new Date(startOfNextMonth)
      endOfMonth.setDate(startOfNextMonth.getDate() - 1)
      this.fromDate = this.convertDateToNgbDate(startOfMonth)
      this.toDate = this.convertDateToNgbDate(endOfMonth)
    }
    this.emitDateRangeChange()
  }


  onDateSelection(date: NgbDate) {
    if (!this.fromDate && !this.toDate) {
      this.fromDate = date
    } else if (this.fromDate && !this.toDate && date && date.after(this.fromDate)) {
      this.toDate = date
    } else {
      this.toDate = null
      this.fromDate = date
    }
    this.convertSelectToDate(this.selectDateRange)
    this.emitDateRangeChange()
  }

  pad(number: number): string {
    return number < 10 ? '0' + number : number.toString()
  }

  emitDateRangeChange() {
    const fromDateStr = this.fromDate ? `${this.fromDate.year}-${this.pad(this.fromDate.month)}-${this.pad(this.fromDate.day)}` : ''
    const toDateStr = this.toDate ? `${this.toDate.year}-${this.pad(this.toDate.month)}-${this.pad(this.toDate.day)}` : ''
    this.dateRangeChange.emit({ fromDate: fromDateStr, toDate: toDateStr })
  }

  isHovered(date: NgbDate) {
    return (
      this.fromDate && !this.toDate && this.hoveredDate && date.after(this.fromDate) && date.before(this.hoveredDate)
    )
  }

  isInside(date: NgbDate) {
    return this.toDate && date.after(this.fromDate) && date.before(this.toDate)
  }

  isRange(date: NgbDate) {
    return (
      date.equals(this.fromDate) ||
      (this.toDate && date.equals(this.toDate)) ||
      this.isInside(date) ||
      this.isHovered(date)
    )
  }

  validateInput(currentValue: NgbDate | null, input: string): NgbDate | null {
    const parsed = this.formatter.parse(input)
    return parsed && this.calendar.isValid(NgbDate.from(parsed)) ? NgbDate.from(parsed) : currentValue
  }

  setDateRange(event: any) {
    const value = event.target.value
    this.convertSelectToDate(value)
  }
}
