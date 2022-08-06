import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import {
  NgbDateParserFormatter,
  NgbDateStruct,
} from '@ng-bootstrap/ng-bootstrap'
import { SettingsService } from 'src/app/services/settings.service'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DateComponent),
      multi: true,
    },
  ],
  selector: 'app-input-date',
  templateUrl: './date.component.html',
  styleUrls: ['./date.component.scss'],
})
export class DateComponent
  extends AbstractInputComponent<string>
  implements OnInit
{
  constructor(
    private settings: SettingsService,
    private ngbDateParserFormatter: NgbDateParserFormatter
  ) {
    super()
  }

  @Input()
  suggestions: Date[]

  getSuggestions() {
    if (this.suggestions == null) return []

    return this.suggestions
      .map((s) => new Date(s)) // required to call the date functions below
      .filter(
        (d) =>
          this.value === null || // if value is not set, take all suggestions
          d.toISOString().slice(0, 10) != this.value // otherwise filter out the current value
      )
      .map((s) =>
        this.ngbDateParserFormatter.format({
          year: s.getFullYear(),
          month: s.getMonth() + 1, // month of Date is zero based
          day: s.getDate(),
        })
      )
  }

  onSuggestionClick(dateString: string) {
    const parsedNgDate = this.ngbDateParserFormatter.parse(dateString)
    this.writeValue(this.formatDateAsYYYYMMDD(parsedNgDate))
    this.onChange(this.value)
  }

  formatDateAsYYYYMMDD(date: NgbDateStruct) {
    const monthPrefix = date.month > 9 ? '' : '0'
    const dayPrefix = date.day > 9 ? '' : '0'
    return `${date.year}-${monthPrefix}${date.month}-${dayPrefix}${date.day}`
  }

  ngOnInit(): void {
    super.ngOnInit()
    this.placeholder = this.settings.getLocalizedDateInputFormat()
  }

  placeholder: string

  onPaste(event: ClipboardEvent) {
    const clipboardData: DataTransfer =
      event.clipboardData || window['clipboardData']
    if (clipboardData) {
      event.preventDefault()
      let pastedText = clipboardData.getData('text')
      pastedText = pastedText.replace(/[\sa-z#!$%\^&\*;:{}=\-_`~()]+/g, '')
      const parsedDate = this.ngbDateParserFormatter.parse(pastedText)
      const formattedDate = this.ngbDateParserFormatter.format(parsedDate)
      this.writeValue(formattedDate)
      this.onChange(formattedDate)
    }
  }

  onKeyPress(event: KeyboardEvent) {
    if ('Enter' !== event.key && !/[0-9,\.\/-]+/.test(event.key)) {
      event.preventDefault()
    }
  }
}
