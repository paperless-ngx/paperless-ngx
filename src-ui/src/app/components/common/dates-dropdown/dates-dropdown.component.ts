import {
  Component,
  EventEmitter,
  Input,
  OnDestroy,
  OnInit,
  Output,
} from '@angular/core'
import { NgbDateAdapter } from '@ng-bootstrap/ng-bootstrap'
import { Subject, Subscription } from 'rxjs'
import { debounceTime } from 'rxjs/operators'
import { SettingsService } from 'src/app/services/settings.service'
import { ISODateAdapter } from 'src/app/utils/ngb-iso-date-adapter'
import { popperOptionsReenablePreventOverflow } from 'src/app/utils/popper-options'

export interface DateSelection {
  createdBefore?: string
  createdAfter?: string
  createdRelativeDateID?: number
  addedBefore?: string
  addedAfter?: string
  addedRelativeDateID?: number
}

export enum RelativeDate {
  LAST_7_DAYS = 0,
  LAST_MONTH = 1,
  LAST_3_MONTHS = 2,
  LAST_YEAR = 3,
}

@Component({
  selector: 'pngx-dates-dropdown',
  templateUrl: './dates-dropdown.component.html',
  styleUrls: ['./dates-dropdown.component.scss'],
  providers: [{ provide: NgbDateAdapter, useClass: ISODateAdapter }],
})
export class DatesDropdownComponent implements OnInit, OnDestroy {
  public popperOptions = popperOptionsReenablePreventOverflow

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

  // created
  @Input()
  createdDateBefore: string

  @Output()
  createdDateBeforeChange = new EventEmitter<string>()

  @Input()
  createdDateAfter: string

  @Output()
  createdDateAfterChange = new EventEmitter<string>()

  @Input()
  createdRelativeDate: RelativeDate

  @Output()
  createdRelativeDateChange = new EventEmitter<number>()

  // added
  @Input()
  addedDateBefore: string

  @Output()
  addedDateBeforeChange = new EventEmitter<string>()

  @Input()
  addedDateAfter: string

  @Output()
  addedDateAfterChange = new EventEmitter<string>()

  @Input()
  addedRelativeDate: RelativeDate

  @Output()
  addedRelativeDateChange = new EventEmitter<number>()

  @Input()
  title: string

  @Output()
  datesSet = new EventEmitter<DateSelection>()

  @Input()
  disabled: boolean = false

  get isActive(): boolean {
    return (
      this.createdRelativeDate !== null ||
      this.createdDateAfter?.length > 0 ||
      this.createdDateBefore?.length > 0 ||
      this.addedRelativeDate !== null ||
      this.addedDateAfter?.length > 0 ||
      this.addedDateBefore?.length > 0
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
    this.createdDateBefore = null
    this.createdDateAfter = null
    this.createdRelativeDate = null
    this.addedDateBefore = null
    this.addedDateAfter = null
    this.addedRelativeDate = null
    this.onChange()
  }

  setCreatedRelativeDate(rd: RelativeDate) {
    this.createdDateBefore = null
    this.createdDateAfter = null
    this.createdRelativeDate = this.createdRelativeDate == rd ? null : rd
    this.onChange()
  }

  setAddedRelativeDate(rd: RelativeDate) {
    this.addedDateBefore = null
    this.addedDateAfter = null
    this.addedRelativeDate = this.addedRelativeDate == rd ? null : rd
    this.onChange()
  }

  onChange() {
    this.createdDateBeforeChange.emit(this.createdDateBefore)
    this.createdDateAfterChange.emit(this.createdDateAfter)
    this.createdRelativeDateChange.emit(this.createdRelativeDate)
    this.addedDateBeforeChange.emit(this.addedDateBefore)
    this.addedDateAfterChange.emit(this.addedDateAfter)
    this.addedRelativeDateChange.emit(this.addedRelativeDate)
    this.datesSet.emit({
      createdAfter: this.createdDateAfter,
      createdBefore: this.createdDateBefore,
      createdRelativeDateID: this.createdRelativeDate,
      addedAfter: this.addedDateAfter,
      addedBefore: this.addedDateBefore,
      addedRelativeDateID: this.addedRelativeDate,
    })
  }

  onChangeDebounce() {
    this.createdRelativeDate = null
    this.addedRelativeDate = null
    this.datesSetDebounce$.next({
      createdAfter: this.createdDateAfter,
      createdBefore: this.createdDateBefore,
      addedAfter: this.addedDateAfter,
      addedBefore: this.addedDateBefore,
    })
  }

  clearCreatedBefore() {
    this.createdDateBefore = null
    this.onChange()
  }

  clearCreatedAfter() {
    this.createdDateAfter = null
    this.onChange()
  }

  clearAddedBefore() {
    this.addedDateBefore = null
    this.onChange()
  }

  clearAddedAfter() {
    this.addedDateAfter = null
    this.onChange()
  }

  // prevent chars other than numbers and separators
  onKeyPress(event: KeyboardEvent) {
    if ('Enter' !== event.key && !/[0-9,\.\/-]+/.test(event.key)) {
      event.preventDefault()
    }
  }
}
