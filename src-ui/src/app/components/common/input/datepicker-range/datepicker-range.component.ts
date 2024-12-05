import { Component, EventEmitter, inject, OnInit, Output } from '@angular/core'
import { NgbCalendar, NgbDate, NgbDateParserFormatter } from '@ng-bootstrap/ng-bootstrap'
import { AbstractInputComponent } from '../abstract-input'
import { SettingsService } from '../../../../services/settings.service'


@Component({
  selector: 'pngx-input-datepicker-range',
  templateUrl: './datepicker-range.component.html',
  styleUrls: ['./datepicker-range.component.scss'],
})
export class DatepickerRangeComponent extends AbstractInputComponent<string>
  implements OnInit {
  @Output() dateRangeChange = new EventEmitter<{ fromDate: string | null, toDate: string | null }>()
  @Output() confirmButton = new EventEmitter()
  calendar = inject(NgbCalendar)
  formatter = inject(NgbDateParserFormatter)

  hoveredDate: NgbDate | null = null
  fromDate: NgbDate | null = this.calendar.getToday()
  toDate: NgbDate | null = this.calendar.getToday()

  constructor(private settings: SettingsService) {
    super()
  }

  ngOnInit() {
    // const dates = this.placeholder.split(" - "); // Tách chuỗi theo dấu " - "
    //
    // let fromDate = dates[0]; // Ngày bắt đầu
    // let toDate = dates[1]; // Ngày kết thúc placeholder.split(" - ");
    // fromDate = this.settings.getLocalizedDateInputFormat()
    // toDate = this.settings.getLocalizedDateInputFormat()
    // this.placeholder = fromDate+" - "+ toDate
    // super.ngOnInit()
    this.emitDateRangeChange()
  }

  isHovered(date: NgbDate) {
    return (
      this.fromDate &&
      !this.toDate &&
      this.hoveredDate &&
      date.after(this.fromDate) &&
      date.before(this.hoveredDate)
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
    return parsed && this.calendar.isValid(NgbDate.from(parsed))
      ? NgbDate.from(parsed)
      : currentValue
  }

  // placeholder: string = ''

  valueInput: string = ''

  onDateSelection(date: NgbDate) {
    if (!this.fromDate && !this.toDate) {
      this.fromDate = date
    } else if (
      (this.fromDate && !this.toDate && date && (date.equals(this.fromDate) ||
          date.after(this.fromDate))
      )) {
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
    // console.log(fromDateStr,toDateStr)
  }


  updateDateRange(value: string) {
    const dates = value.split(' to ')
    if (dates.length === 2) {
      this.fromDate = this.parseDate(dates[0])
      this.toDate = this.parseDate(dates[1])
    }
  }

  parseDate(dateStr: string): NgbDate {
    const parts = dateStr.split('-')
    return new NgbDate(+parts[0], +parts[1], +parts[2])
  }

  setRange(range: string) {
    const today = new NgbDate(new Date().getFullYear(), new Date().getMonth() + 1, new Date().getDate())

    switch (range) {
      case 'today':
        this.fromDate = today
        this.toDate = today
        this.emitDateRangeChange()
        break
      case 'yesterday':
        const yesterday = new Date()
        yesterday.setDate(yesterday.getDate() - 1)
        this.fromDate = new NgbDate(yesterday.getFullYear(), yesterday.getMonth() + 1, yesterday.getDate())
        this.toDate = this.fromDate
        this.emitDateRangeChange()
        break
      case 'last7days':
        const last7Days = new Date()
        last7Days.setDate(last7Days.getDate() - 7)
        this.fromDate = new NgbDate(last7Days.getFullYear(), last7Days.getMonth() + 1, last7Days.getDate())
        this.toDate = today
        this.emitDateRangeChange()
        break
      case 'last30days':
        const last30Days = new Date()
        last30Days.setDate(last30Days.getDate() - 30)
        this.fromDate = new NgbDate(last30Days.getFullYear(), last30Days.getMonth() + 1, last30Days.getDate())
        this.toDate = today
        this.emitDateRangeChange()
        break
      case 'thisMonth':
        this.fromDate = new NgbDate(today.year, today.month, 1)
        this.toDate = today
        this.emitDateRangeChange()
        break
      case 'lastMonth':
        const firstDayOfCurrentMonth = new Date(today.year, today.month - 1, 1)
        // Tính ngày cuối cùng của tháng trước
        const lastDayOfLastMonth = new Date(firstDayOfCurrentMonth.getTime() - 1)
        // Gán giá trị cho fromDate và toDate
        this.fromDate = new NgbDate(lastDayOfLastMonth.getFullYear(), lastDayOfLastMonth.getMonth() + 1, 1) // Ngày đầu tiên của tháng trước
        this.toDate = new NgbDate(lastDayOfLastMonth.getFullYear(), lastDayOfLastMonth.getMonth() + 1, lastDayOfLastMonth.getDate())
        this.emitDateRangeChange()
        break

    }
  }
}
