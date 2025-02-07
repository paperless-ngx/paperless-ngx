import {
  Component,
  EventEmitter,
  forwardRef,
  Input,
  OnInit,
  Output,
} from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { RouterModule } from '@angular/router'
import {
  NgbDateAdapter,
  NgbDateParserFormatter,
  NgbDatepickerModule,
  NgbDateStruct,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
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
  imports: [
    NgbDatepickerModule,
    FormsModule,
    ReactiveFormsModule,
    RouterModule,
    NgxBootstrapIconsModule,
  ],
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

  public readonly today: string = new Date().toISOString().split('T')[0]

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
    if (
      'Enter' !== event.key &&
      !(event.altKey || event.metaKey || event.ctrlKey) &&
      !/[0-9,\.\/-]+/.test(event.key)
    ) {
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
