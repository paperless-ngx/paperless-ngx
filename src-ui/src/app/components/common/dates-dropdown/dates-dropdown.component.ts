import { NgClass, NgTemplateOutlet } from '@angular/common'
import {
  Component,
  EventEmitter,
  Input,
  OnDestroy,
  OnInit,
  Output,
  inject,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbDateAdapter,
  NgbDatepickerModule,
  NgbDropdownModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, Subscription } from 'rxjs'
import { debounceTime } from 'rxjs/operators'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { SettingsService } from 'src/app/services/settings.service'
import { ISODateAdapter } from 'src/app/utils/ngb-iso-date-adapter'
import { pngxPopperOptions } from 'src/app/utils/popper-options'
import { ClearableBadgeComponent } from '../clearable-badge/clearable-badge.component'

export interface DateSelection {
  createdTo?: string
  createdFrom?: string
  createdRelativeDateID?: number
  addedTo?: string
  addedFrom?: string
  addedRelativeDateID?: number
}

export enum RelativeDate {
  WITHIN_1_WEEK = 1,
  WITHIN_1_MONTH = 2,
  WITHIN_3_MONTHS = 3,
  WITHIN_1_YEAR = 4,
  THIS_YEAR = 5,
  THIS_MONTH = 6,
  TODAY = 7,
  YESTERDAY = 8,
  PREVIOUS_WEEK = 9,
  PREVIOUS_MONTH = 10,
  PREVIOUS_QUARTER = 11,
  PREVIOUS_YEAR = 12,
}

@Component({
  selector: 'pngx-dates-dropdown',
  templateUrl: './dates-dropdown.component.html',
  styleUrls: ['./dates-dropdown.component.scss'],
  providers: [{ provide: NgbDateAdapter, useClass: ISODateAdapter }],
  imports: [
    ClearableBadgeComponent,
    CustomDatePipe,
    NgxBootstrapIconsModule,
    NgbDatepickerModule,
    NgbDropdownModule,
    NgSelectModule,
    FormsModule,
    ReactiveFormsModule,
    NgClass,
    NgTemplateOutlet,
  ],
})
export class DatesDropdownComponent implements OnInit, OnDestroy {
  public popperOptions = pngxPopperOptions

  constructor() {
    const settings = inject(SettingsService)

    this.datePlaceHolder = settings.getLocalizedDateInputFormat()
  }

  relativeDates = [
    {
      id: RelativeDate.WITHIN_1_WEEK,
      name: $localize`Within 1 week`,
      dateTilNow: new Date().setDate(new Date().getDate() - 7),
    },
    {
      id: RelativeDate.WITHIN_1_MONTH,
      name: $localize`Within 1 month`,
      dateTilNow: new Date().setMonth(new Date().getMonth() - 1),
    },
    {
      id: RelativeDate.WITHIN_3_MONTHS,
      name: $localize`Within 3 months`,
      dateTilNow: new Date().setMonth(new Date().getMonth() - 3),
    },
    {
      id: RelativeDate.WITHIN_1_YEAR,
      name: $localize`Within 1 year`,
      dateTilNow: new Date().setFullYear(new Date().getFullYear() - 1),
    },
    {
      id: RelativeDate.THIS_YEAR,
      name: $localize`This year`,
      date: new Date('1/1/' + new Date().getFullYear()),
      dateEnd: new Date('12/31/' + new Date().getFullYear()),
    },
    {
      id: RelativeDate.THIS_MONTH,
      name: $localize`This month`,
      date: new Date().setDate(1),
      dateEnd: new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0),
    },
    {
      id: RelativeDate.TODAY,
      name: $localize`Today`,
      date: new Date().setHours(0, 0, 0, 0),
    },
    {
      id: RelativeDate.YESTERDAY,
      name: $localize`Yesterday`,
      date: new Date().setDate(new Date().getDate() - 1),
    },
    {
      id: RelativeDate.PREVIOUS_WEEK,
      name: $localize`Previous week`,
      date: new Date(
        new Date().getFullYear(),
        new Date().getMonth(),
        new Date().getDate() - new Date().getDay() - 6
      ),
      dateEnd: new Date(
        new Date().getFullYear(),
        new Date().getMonth(),
        new Date().getDate() - new Date().getDay()
      ),
    },
    {
      id: RelativeDate.PREVIOUS_MONTH,
      name: $localize`Previous month`,
      date: new Date(new Date().getFullYear(), new Date().getMonth() - 1, 1),
      dateEnd: new Date(new Date().getFullYear(), new Date().getMonth(), 0),
    },
    {
      id: RelativeDate.PREVIOUS_QUARTER,
      name: $localize`Previous quarter`,
      date: new Date(
        new Date().getFullYear(),
        Math.floor(new Date().getMonth() / 3) * 3 - 3,
        1
      ),
      dateEnd: new Date(
        new Date().getFullYear(),
        Math.floor(new Date().getMonth() / 3) * 3,
        0
      ),
    },
    {
      id: RelativeDate.PREVIOUS_YEAR,
      name: $localize`Previous year`,
      date: new Date('1/1/' + (new Date().getFullYear() - 1)),
      dateEnd: new Date('12/31/' + (new Date().getFullYear() - 1)),
    },
  ]

  datePlaceHolder: string

  // created
  @Input()
  createdDateTo: string = null

  @Output()
  createdDateToChange = new EventEmitter<string>()

  @Input()
  createdDateFrom: string = null

  @Output()
  createdDateFromChange = new EventEmitter<string>()

  @Input()
  createdRelativeDate: RelativeDate = null

  @Output()
  createdRelativeDateChange = new EventEmitter<number>()

  // added
  @Input()
  addedDateTo: string = null

  @Output()
  addedDateToChange = new EventEmitter<string>()

  @Input()
  addedDateFrom: string = null

  @Output()
  addedDateFromChange = new EventEmitter<string>()

  @Input()
  addedRelativeDate: RelativeDate = null

  @Output()
  addedRelativeDateChange = new EventEmitter<number>()

  @Input()
  title: string

  @Output()
  datesSet = new EventEmitter<DateSelection>()

  @Input()
  disabled: boolean = false

  @Input()
  placement: string = 'bottom-start'

  public readonly today: string = new Date().toLocaleDateString('en-CA')

  get isActive(): boolean {
    return (
      this.createdRelativeDate !== null ||
      this.createdDateFrom?.length > 0 ||
      this.createdDateTo?.length > 0 ||
      this.addedRelativeDate !== null ||
      this.addedDateFrom?.length > 0 ||
      this.addedDateTo?.length > 0
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
    this.createdDateTo = null
    this.createdDateFrom = null
    this.createdRelativeDate = null
    this.addedDateTo = null
    this.addedDateFrom = null
    this.addedRelativeDate = null
    this.onChange()
  }

  onSetCreatedRelativeDate(rd: { id: number; name: string; date: number }) {
    // createdRelativeDate is set by ngModel
    this.createdDateTo = null
    this.createdDateFrom = null
    this.onChange()
  }

  onSetAddedRelativeDate(rd: { id: number; name: string; date: number }) {
    // addedRelativeDate is set by ngModel
    this.addedDateTo = null
    this.addedDateFrom = null
    this.onChange()
  }

  onChange() {
    this.createdDateToChange.emit(this.createdDateTo)
    this.createdDateFromChange.emit(this.createdDateFrom)
    this.createdRelativeDateChange.emit(this.createdRelativeDate)
    this.addedDateToChange.emit(this.addedDateTo)
    this.addedDateFromChange.emit(this.addedDateFrom)
    this.addedRelativeDateChange.emit(this.addedRelativeDate)
    this.datesSet.emit({
      createdFrom: this.createdDateFrom,
      createdTo: this.createdDateTo,
      createdRelativeDateID: this.createdRelativeDate,
      addedFrom: this.addedDateFrom,
      addedTo: this.addedDateTo,
      addedRelativeDateID: this.addedRelativeDate,
    })
  }

  onChangeDebounce() {
    this.createdRelativeDate = null
    this.addedRelativeDate = null
    this.datesSetDebounce$.next({
      createdAfter: this.createdDateFrom,
      createdBefore: this.createdDateTo,
      addedAfter: this.addedDateFrom,
      addedBefore: this.addedDateTo,
    })
  }

  clearCreatedTo() {
    this.createdDateTo = null
    this.onChange()
  }

  clearCreatedFrom() {
    this.createdDateFrom = null
    this.onChange()
  }

  clearCreatedRelativeDate() {
    this.createdRelativeDate = null
    this.onChange()
  }

  clearAddedTo() {
    this.addedDateTo = null
    this.onChange()
  }

  clearAddedFrom() {
    this.addedDateFrom = null
    this.onChange()
  }

  clearAddedRelativeDate() {
    this.addedRelativeDate = null
    this.onChange()
  }

  // prevent chars other than numbers and separators
  onKeyPress(event: KeyboardEvent) {
    if ('Enter' !== event.key && !/[0-9,\.\/-]+/.test(event.key)) {
      event.preventDefault()
    }
  }
}
