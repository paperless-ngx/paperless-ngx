import { formatDate } from '@angular/common';
import { Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { NgbDateAdapter } from '@ng-bootstrap/ng-bootstrap';
import { Subject, Subscription } from 'rxjs';
import { debounceTime } from 'rxjs/operators';
import { SettingsService } from 'src/app/services/settings.service';
import { ISODateAdapter } from 'src/app/utils/ngb-iso-date-adapter';

export interface DateSelection {
  before?: string
  after?: string
}

const LAST_7_DAYS = 0
const LAST_MONTH = 1
const LAST_3_MONTHS = 2
const LAST_YEAR = 3

@Component({
  selector: 'app-date-dropdown',
  templateUrl: './date-dropdown.component.html',
  styleUrls: ['./date-dropdown.component.scss'],
  providers: [
    {provide: NgbDateAdapter, useClass: ISODateAdapter},
  ]
})
export class DateDropdownComponent implements OnInit, OnDestroy {

  constructor(settings: SettingsService) {
    this.datePlaceHolder = settings.getLocalizedDateInputFormat()
  }

  quickFilters = [
    {id: LAST_7_DAYS, name: $localize`Last 7 days`},
    {id: LAST_MONTH, name: $localize`Last month`},
    {id: LAST_3_MONTHS, name: $localize`Last 3 months`},
    {id: LAST_YEAR, name: $localize`Last year`}
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
  title: string

  @Output()
  datesSet = new EventEmitter<DateSelection>()

  private datesSetDebounce$ = new Subject()

  private sub: Subscription

  ngOnInit() {
    this.sub = this.datesSetDebounce$.pipe(
      debounceTime(400)
    ).subscribe(() => {
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
    let date = new Date()
    switch (qf) {
      case LAST_7_DAYS:
        date.setDate(date.getDate() - 7)
        break;

      case LAST_MONTH:
        date.setMonth(date.getMonth() - 1)
        break;

      case LAST_3_MONTHS:
        date.setMonth(date.getMonth() - 3)
        break

      case LAST_YEAR:
        date.setFullYear(date.getFullYear() - 1)
        break

      }
    this.dateAfter = formatDate(date, 'yyyy-MM-dd', "en-us", "UTC")
    this.onChange()
  }

  onChange() {
    this.dateAfterChange.emit(this.dateAfter)
    this.dateBeforeChange.emit(this.dateBefore)
    this.datesSet.emit({after: this.dateAfter, before: this.dateBefore})
  }

  onChangeDebounce() {
    this.datesSetDebounce$.next({after: this.dateAfter, before: this.dateBefore})
  }

  clearBefore() {
    this.dateBefore = null
    this.onChange()
  }

  clearAfter() {
    this.dateAfter = null
    this.onChange()
  }

}
