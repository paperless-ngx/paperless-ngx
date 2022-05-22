import { Component, forwardRef, OnInit } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { NgbDateParserFormatter } from '@ng-bootstrap/ng-bootstrap'
import { SettingsService } from 'src/app/services/settings.service'
import { LocalizedDateParserFormatter } from 'src/app/utils/ngb-date-parser-formatter'
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
