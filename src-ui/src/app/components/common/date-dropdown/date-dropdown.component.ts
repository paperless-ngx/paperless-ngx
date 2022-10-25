import { formatDate } from '@angular/common'
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
  dateQuery?: string
}

interface QuickFilter {
  id: number
  name: string
  dateQuery: string
}

const LAST_7_DAYS = 0
const LAST_MONTH = 1
const LAST_3_MONTHS = 2
const LAST_YEAR = 3

@Component({
  selector: 'app-date-dropdown',
  templateUrl: './date-dropdown.component.html',
  styleUrls: ['./date-dropdown.component.scss'],
  providers: [{ provide: NgbDateAdapter, useClass: ISODateAdapter }],
})
export class DateDropdownComponent implements OnInit, OnDestroy {
  constructor(settings: SettingsService) {
    this.datePlaceHolder = settings.getLocalizedDateInputFormat()
  }

  quickFilters: Array<QuickFilter> = [
    {
      id: LAST_7_DAYS,
      name: $localize`Last 7 days`,
      dateQuery: '-1 week to now',
    },
    {
      id: LAST_MONTH,
      name: $localize`Last month`,
      dateQuery: '-1 month to now',
    },
    {
      id: LAST_3_MONTHS,
      name: $localize`Last 3 months`,
      dateQuery: '-3 month to now',
    },
    { id: LAST_YEAR, name: $localize`Last year`, dateQuery: '-1 year to now' },
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

  quickFilter: number

  @Input()
  set dateQuery(query: string) {
    this.quickFilter = this.quickFilters.find((qf) => qf.dateQuery == query)?.id
  }

  get dateQuery(): string {
    return (
      this.quickFilters.find((qf) => qf.id == this.quickFilter)?.dateQuery ?? ''
    )
  }

  @Output()
  dateQueryChange = new EventEmitter<string>()

  @Input()
  title: string

  @Output()
  datesSet = new EventEmitter<DateSelection>()

  get isActive(): boolean {
    return (
      this.quickFilter > -1 ||
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

  setDateQuickFilter(qf: number) {
    this.dateBefore = null
    this.dateAfter = null
    this.quickFilter = this.quickFilter == qf ? null : qf
    this.onChange()
  }

  qfIsSelected(qf: number) {
    return this.quickFilter == qf
  }

  onChange() {
    this.dateBeforeChange.emit(this.dateBefore)
    this.dateAfterChange.emit(this.dateAfter)
    this.dateQueryChange.emit(this.dateQuery)
    this.datesSet.emit({
      after: this.dateAfter,
      before: this.dateBefore,
      dateQuery: this.dateQuery,
    })
  }

  onChangeDebounce() {
    this.dateQuery = null
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
