import {
  Component,
  EventEmitter,
  forwardRef,
  Input,
  OnInit,
  Output,
} from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import {
  NgbDateAdapter,
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
  selector: 'pngx-input-date',
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

  @Input()
  showFilter: boolean = false

  @Output()
  filterDocuments = new EventEmitter<NgbDateStruct[]>()

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
      if (parsedDate) {
        this.writeValue(this.isoDateAdapter.toModel(parsedDate))
        this.onChange(this.value)
      }
    }
  }

  onKeyPress(event: KeyboardEvent) {
    if ('Enter' !== event.key && !/[0-9,\.\/-]+/.test(event.key)) {
      event.preventDefault()
    }
  }

  onFilterDocuments() {
    this.filterDocuments.emit([this.ngbDateParserFormatter.parse(this.value)])
  }

  get filterButtonTitle() {
    return $localize`Filter documents with this ${this.title}`
  }
}
