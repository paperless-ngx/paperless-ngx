import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import {
  NgbDateAdapter,
  NgbDateParserFormatter,
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
    private ngbDateParserFormatter: NgbDateParserFormatter,
    private isoDateAdapter: NgbDateAdapter<string>
  ) {
    super()
  }

  @Input()
  suggestions: string[]

  getSuggestions() {
    return this.suggestions == null
      ? []
      : this.suggestions
          .map((s) => this.ngbDateParserFormatter.parse(s))
          .filter(
            (d) =>
              this.value === null || // if value is not set, take all suggestions
              this.value != this.isoDateAdapter.toModel(d) // otherwise filter out current date
          )
          .map((s) => this.ngbDateParserFormatter.format(s))
  }

  onSuggestionClick(dateString: string) {
    const parsedDate = this.ngbDateParserFormatter.parse(dateString)
    this.writeValue(this.isoDateAdapter.toModel(parsedDate))
    this.onChange(this.value)
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
