import { NgClass } from '@angular/common'
import {
  Component,
  EventEmitter,
  Input,
  OnDestroy,
  OnInit,
  Output,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbDateAdapter,
  NgbDatepickerModule,
  NgbDropdownModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, Subscription } from 'rxjs'
import { debounceTime } from 'rxjs/operators'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { SettingsService } from 'src/app/services/settings.service'
import { ISODateAdapter } from 'src/app/utils/ngb-iso-date-adapter'
import { popperOptionsReenablePreventOverflow } from 'src/app/utils/popper-options'
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
  WITHIN_1_WEEK = 0,
  WITHIN_1_MONTH = 1,
  WITHIN_3_MONTHS = 2,
  WITHIN_1_YEAR = 3,
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
    FormsModule,
    ReactiveFormsModule,
    NgClass,
  ],
})
export class DatesDropdownComponent implements OnInit, OnDestroy {
  public popperOptions = popperOptionsReenablePreventOverflow

  constructor(settings: SettingsService) {
    this.datePlaceHolder = settings.getLocalizedDateInputFormat()
  }

  relativeDates = [
    {
      id: RelativeDate.WITHIN_1_WEEK,
      name: $localize`Within 1 week`,
      date: new Date().setDate(new Date().getDate() - 7),
    },
    {
      id: RelativeDate.WITHIN_1_MONTH,
      name: $localize`Within 1 month`,
      date: new Date().setMonth(new Date().getMonth() - 1),
    },
    {
      id: RelativeDate.WITHIN_3_MONTHS,
      name: $localize`Within 3 months`,
      date: new Date().setMonth(new Date().getMonth() - 3),
    },
    {
      id: RelativeDate.WITHIN_1_YEAR,
      name: $localize`Within 1 year`,
      date: new Date().setFullYear(new Date().getFullYear() - 1),
    },
  ]

  datePlaceHolder: string

  // created
  @Input()
  createdDateTo: string

  @Output()
  createdDateToChange = new EventEmitter<string>()

  @Input()
  createdDateFrom: string

  @Output()
  createdDateFromChange = new EventEmitter<string>()

  @Input()
  createdRelativeDate: RelativeDate

  @Output()
  createdRelativeDateChange = new EventEmitter<number>()

  // added
  @Input()
  addedDateTo: string

  @Output()
  addedDateToChange = new EventEmitter<string>()

  @Input()
  addedDateFrom: string

  @Output()
  addedDateFromChange = new EventEmitter<string>()

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

  public readonly today: string = new Date().toISOString().split('T')[0]

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

  setCreatedRelativeDate(rd: RelativeDate) {
    this.createdDateTo = null
    this.createdDateFrom = null
    this.createdRelativeDate = this.createdRelativeDate == rd ? null : rd
    this.onChange()
  }

  setAddedRelativeDate(rd: RelativeDate) {
    this.addedDateTo = null
    this.addedDateFrom = null
    this.addedRelativeDate = this.addedRelativeDate == rd ? null : rd
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

  clearAddedTo() {
    this.addedDateTo = null
    this.onChange()
  }

  clearAddedFrom() {
    this.addedDateFrom = null
    this.onChange()
  }

  // prevent chars other than numbers and separators
  onKeyPress(event: KeyboardEvent) {
    if ('Enter' !== event.key && !/[0-9,\.\/-]+/.test(event.key)) {
      event.preventDefault()
    }
  }
}
