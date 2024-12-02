import { Component, EventEmitter, inject, Input, OnInit, Output } from '@angular/core'
import { NgbCalendar, NgbDate, NgbDateParserFormatter, NgbDateStruct } from '@ng-bootstrap/ng-bootstrap'
import { FormsModule } from '@angular/forms'
import { JsonPipe } from '@angular/common'
import { AbstractInputComponent } from '../abstract-input'
import { end } from '@popperjs/core'
import { SettingsService } from '../../../../services/settings.service'


@Component({
  selector: 'pngx-input-datepicker-range',
  templateUrl: './datepicker-range.component.html',
  styleUrls: ['./datepicker-range.component.scss'],
})
export class DatepickerRangeComponent extends AbstractInputComponent<string>
  implements OnInit {
  calendar = inject(NgbCalendar)
  formatter = inject(NgbDateParserFormatter)
  today = new Date()
  tomorrow = new Date()
  @Output() dateRangeChange = new EventEmitter<{ fromDate: string | null, toDate: string | null }>()
  @Output() confirmButton = new EventEmitter()

  protected hoveredDate: NgbDate | null = null
  protected fromDate: NgbDate | null = this.calendar.getToday()
  protected toDate: NgbDate | null = this.calendar.getNext(this.calendar.getToday(), 'd', 10)
  protected minDate: NgbDateStruct
  protected maxDate: NgbDateStruct
  protected placeholder: string

  constructor(private settings: SettingsService,) {
    super()
  }
  ngOnInit() {
    this.minDate = { year: 1900, month: 1, day: 1 }
    this.maxDate = { year: 2100, month: 12, day: 31 }
    this.tomorrow.setDate(this.today.getDate() + 1)
    this.fromDate = this.convertDateToNgbDate(this.today)
    this.toDate = this.convertDateToNgbDate(this.today)
    // this.emitDateRangeChange()
    this.placeholder = this.settings.getLocalizedDateInputFormat()
    super.ngOnInit()
  }

  convertDateToNgbDate(date: Date): NgbDate {
    return new NgbDate(date.getFullYear(), date.getMonth() + 1, date.getDate())
  }


  onDateRangeSelection(date: NgbDate) {
    if (!this.fromDate && !this.toDate) {
      this.fromDate = date
    } else if (this.fromDate && !this.toDate && date && date.after(this.fromDate)) {
      this.toDate = date
    } else {
      this.toDate = null
      this.fromDate = date
    }
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


  getThisWeek() {
    const startOfWeek = new Date(this.today)
    startOfWeek.setDate(this.today.getDate() - this.today.getDay() + 1)
    this.fromDate = this.convertDateToNgbDate(startOfWeek)
    const endOfWeek = new Date(startOfWeek)
    endOfWeek.setDate(startOfWeek.getDate() + 6)
    this.toDate = this.convertDateToNgbDate(endOfWeek)
    this.emitDateRangeChange()
  }

  getThisMonth() {
    const startOfMonth = new Date(this.today.getFullYear(), this.today.getMonth(), 1)
    const startOfNextMonth = new Date(this.today.getFullYear(), this.today.getMonth() + 1, 1)
    const endOfMonth = new Date(startOfNextMonth)
    endOfMonth.setDate(startOfNextMonth.getDate() - 1)
    this.fromDate = this.convertDateToNgbDate(startOfMonth)
    this.toDate = this.convertDateToNgbDate(endOfMonth)
    this.emitDateRangeChange()
  }

  getThisYear() {
    const startOfYear = new Date(this.today.getFullYear(), 0, 1) // Ngày 1 tháng 1 của năm hiện tại
    const startOfNextYear = new Date(this.today.getFullYear() + 1, 0, 1) // Ngày 1 tháng 1 của năm tiếp theo
    const endOfYear = new Date(startOfNextYear)
    endOfYear.setDate(startOfNextYear.getDate() - 1) // Ngày cuối cùng của năm hiện tại

    this.fromDate = this.convertDateToNgbDate(startOfYear)
    this.toDate = this.convertDateToNgbDate(endOfYear)
    this.emitDateRangeChange()
  }

}
