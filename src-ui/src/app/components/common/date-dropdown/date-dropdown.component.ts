import {
  Component,
  EventEmitter,
  Input,
  Output,
  OnInit,
  OnDestroy,
} from '@angular/core'
import { NgbDateAdapter } from '@ng-bootstrap/ng-bootstrap'
import { Subject, Subscription } from 'rxjs'
import { debounceTime } from 'rxjs/operators'
import { SettingsService } from 'src/app/services/settings.service'
import { ISODateAdapter } from 'src/app/utils/ngb-iso-date-adapter'

export interface DateSelection {
  before?: string
  after?: string
  relativeDateID?: number
}

export enum RelativeDate {
  LAST_7_DAYS = 0,
  LAST_MONTH = 1,
  LAST_3_MONTHS = 2,
  LAST_YEAR = 3,
}

@Component({
  selector: 'pngx-date-dropdown',
  templateUrl: './date-dropdown.component.html',
  styleUrls: ['./date-dropdown.component.scss'],
  providers: [{ provide: NgbDateAdapter, useClass: ISODateAdapter }],
})
export class DateDropdownComponent implements OnInit, OnDestroy {
  constructor(settings: SettingsService) {
    this.datePlaceHolder = settings.getLocalizedDateInputFormat()
  }

  relativeDates = [
    {
      id: RelativeDate.LAST_7_DAYS,
      name: $localize`Last 7 days`,
      date: new Date().setDate(new Date().getDate() - 7),
    },
    {
      id: RelativeDate.LAST_MONTH,
      name: $localize`Last month`,
      date: new Date().setMonth(new Date().getMonth() - 1),
    },
    {
      id: RelativeDate.LAST_3_MONTHS,
      name: $localize`Last 3 months`,
      date: new Date().setMonth(new Date().getMonth() - 3),
    },
    {
      id: RelativeDate.LAST_YEAR,
      name: $localize`Last year`,
      date: new Date().setFullYear(new Date().getFullYear() - 1),
    },
  ]

  datePlaceHolder: string

  @Input()
  dateBefore: string

  @Output()
  dateBeforeChange = new EventEmitter<string>()

  @Input()
  dateAfter: string

  @Output()
  dateAfterChange = new EventEmitter<string>()

  @Input()
  relativeDate: RelativeDate

  @Output()
  relativeDateChange = new EventEmitter<number>()

  @Input()
  title: string

  @Output()
  datesSet = new EventEmitter<DateSelection>()

  @Input()
  disabled: boolean = false

  get isActive(): boolean {
    return (
      this.relativeDate !== null ||
      this.dateAfter?.length > 0 ||
      this.dateBefore?.length > 0
    )
  }

  private datesSetDebounce$ = new Subject()

  private sub: Subscription

  ngOnInit() {
    this.sub = this.datesSetDebounce$.pipe(debounceTime(400)).subscribe(() => {
      this.onChange()
    })
  }

  ngOnDestroy() {
    if (this.sub) {
      this.sub.unsubscribe()
    }
  }

  reset() {
    this.dateBefore = null
    this.dateAfter = null
    this.relativeDate = null
    this.onChange()
  }

  setRelativeDate(rd: RelativeDate) {
    this.dateBefore = null
    this.dateAfter = null
    this.relativeDate = this.relativeDate == rd ? null : rd
    this.onChange()
  }

  onChange() {
    this.dateBeforeChange.emit(this.dateBefore)
    this.dateAfterChange.emit(this.dateAfter)
    this.relativeDateChange.emit(this.relativeDate)
    this.datesSet.emit({
      after: this.dateAfter,
      before: this.dateBefore,
      relativeDateID: this.relativeDate,
    })
  }

  onChangeDebounce() {
    this.relativeDate = null
    this.datesSetDebounce$.next({
      after: this.dateAfter,
      before: this.dateBefore,
    })
  }

  clearBefore() {
    this.dateBefore = null
    this.onChange()
  }

  clearAfter() {
    this.dateAfter = null
    this.onChange()
  }

  // prevent chars other than numbers and separators
  onKeyPress(event: KeyboardEvent) {
    if ('Enter' !== event.key && !/[0-9,\.\/-]+/.test(event.key)) {
      event.preventDefault()
    }
  }
}
