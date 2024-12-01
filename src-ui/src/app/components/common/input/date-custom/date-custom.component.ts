import { Component, EventEmitter, forwardRef, inject, Input, OnInit, Output } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { NgbCalendar, NgbDate, NgbDateStruct } from '@ng-bootstrap/ng-bootstrap'
import { AbstractInputComponent } from '../abstract-input'
import { SettingsService } from '../../../../services/settings.service'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DateCustomComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-date-custom',
  templateUrl: './date-custom.component.html',
  styleUrls: ['./date-custom.component.scss'],
})
export class DateCustomComponent extends AbstractInputComponent<string> implements OnInit {
  @Output() dateSelection = new EventEmitter<NgbDate>()
  @Input() model: string
  today = inject(NgbCalendar).getToday()

  constructor(
    private settings: SettingsService,
  ) {
    super()
  }

  convertNgbDateToString(date: NgbDate): string {
    if (!date) {
      return '';
    }
    const year = date.year;
    const month = date.month < 10 ? `0${date.month}` : date.month;
    const day = date.day < 10 ? `0${date.day}` : date.day;
    return `${year}-${month}-${day}`;
  }


  ngOnInit(): void {
    this.placeholder = this.settings.getLocalizedDateInputFormat()
    this.model = this.convertNgbDateToString(this.today)
    super.ngOnInit()
  }

  placeholder: string

  onDateSelection(date: NgbDate) {
    this.dateSelection.emit(date)
  }

  setToday(){
    this.model = this.convertNgbDateToString(this.today)
    this.onDateSelection(this.today)
  }

}
