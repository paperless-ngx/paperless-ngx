import { DatePipe } from '@angular/common'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { SettingsService } from 'src/app/services/settings.service'
import { ClearableBadgeComponent } from '../clearable-badge/clearable-badge.component'
import {
  DateSelection,
  DatesDropdownComponent,
  RelativeDate,
} from './dates-dropdown.component'
let fixture: ComponentFixture<DatesDropdownComponent>

describe('DatesDropdownComponent', () => {
  let component: DatesDropdownComponent
  let settingsService: SettingsService
  let settingsSpy

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
        DatesDropdownComponent,
        ClearableBadgeComponent,
        CustomDatePipe,
      ],
      providers: [
        SettingsService,
        CustomDatePipe,
        DatePipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    settingsService = TestBed.inject(SettingsService)
    settingsSpy = jest.spyOn(settingsService, 'getLocalizedDateInputFormat')

    fixture = TestBed.createComponent(DatesDropdownComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should use a localized date placeholder', () => {
    expect(component.datePlaceHolder).toEqual('mm/dd/yyyy')
    expect(settingsSpy).toHaveBeenCalled()
  })

  it('should support date input, emit change', fakeAsync(() => {
    let result: string
    component.createdDateFromChange.subscribe((date) => (result = date))
    const input: HTMLInputElement = fixture.nativeElement.querySelector('input')
    input.value = '5/30/2023'
    input.dispatchEvent(new Event('change'))
    tick(500)
    expect(result).not.toBeNull()
  }))

  it('should support date select, emit datesSet change', fakeAsync(() => {
    let result: DateSelection
    component.datesSet.subscribe((date) => (result = date))
    const input: HTMLInputElement = fixture.nativeElement.querySelector('input')
    input.value = '5/30/2023'
    input.dispatchEvent(new Event('dateSelect'))
    tick(500)
    expect(result).not.toBeNull()
  }))

  it('should support relative dates', fakeAsync(() => {
    let result: DateSelection
    component.datesSet.subscribe((date) => (result = date))
    component.createdRelativeDate = RelativeDate.WITHIN_1_WEEK // normally set by ngModel binding in dropdown
    component.onSetCreatedRelativeDate({
      id: RelativeDate.WITHIN_1_WEEK,
    } as any)
    component.addedRelativeDate = RelativeDate.WITHIN_1_WEEK // normally set by ngModel binding in dropdown
    component.onSetAddedRelativeDate({ id: RelativeDate.WITHIN_1_WEEK } as any)
    tick(500)
    expect(result).toEqual({
      createdFrom: null,
      createdTo: null,
      createdRelativeDateID: RelativeDate.WITHIN_1_WEEK,
      addedFrom: null,
      addedTo: null,
      addedRelativeDateID: RelativeDate.WITHIN_1_WEEK,
    })
  }))

  it('should support report if active', () => {
    component.createdRelativeDate = RelativeDate.WITHIN_1_WEEK
    expect(component.isActive).toBeTruthy()
    component.createdRelativeDate = null
    component.createdDateFrom = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.createdDateFrom = null
    component.createdDateTo = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.createdDateTo = null

    component.addedRelativeDate = RelativeDate.WITHIN_1_WEEK
    expect(component.isActive).toBeTruthy()
    component.addedRelativeDate = null
    component.addedDateFrom = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.addedDateFrom = null
    component.addedDateTo = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.addedDateTo = null

    expect(component.isActive).toBeFalsy()
  })

  it('should support reset', () => {
    component.createdDateFrom = '2023-05-30'
    component.reset()
    expect(component.createdDateFrom).toBeNull()
  })

  it('should support clearFrom', () => {
    component.createdDateFrom = '2023-05-30'
    component.clearCreatedFrom()
    expect(component.createdDateFrom).toBeNull()

    component.addedDateFrom = '2023-05-30'
    component.clearAddedFrom()
    expect(component.addedDateFrom).toBeNull()
  })

  it('should support clearTo', () => {
    component.createdDateTo = '2023-05-30'
    component.clearCreatedTo()
    expect(component.createdDateTo).toBeNull()

    component.addedDateTo = '2023-05-30'
    component.clearAddedTo()
    expect(component.addedDateTo).toBeNull()
  })

  it('should support clearRelativeDate', () => {
    component.createdRelativeDate = RelativeDate.WITHIN_1_WEEK
    component.clearCreatedRelativeDate()
    expect(component.createdRelativeDate).toBeNull()

    component.addedRelativeDate = RelativeDate.WITHIN_1_WEEK
    component.clearAddedRelativeDate()
    expect(component.addedRelativeDate).toBeNull()
  })

  it('should limit keyboard events', () => {
    const input: HTMLInputElement =
      fixture.nativeElement.querySelector('input.form-control')
    let event: KeyboardEvent = new KeyboardEvent('keypress', {
      key: '9',
    })
    let eventSpy = jest.spyOn(event, 'preventDefault')
    input.dispatchEvent(event)
    expect(eventSpy).not.toHaveBeenCalled()

    event = new KeyboardEvent('keypress', {
      key: '{',
    })
    eventSpy = jest.spyOn(event, 'preventDefault')
    input.dispatchEvent(event)
    expect(eventSpy).toHaveBeenCalled()
  })

  it('should support debounce', fakeAsync(() => {
    let result: DateSelection
    component.datesSet.subscribe((date) => (result = date))
    component.onChangeDebounce()
    tick(500)
    expect(result).toEqual({
      createdFrom: null,
      createdTo: null,
      createdRelativeDateID: null,
      addedFrom: null,
      addedTo: null,
      addedRelativeDateID: null,
    })
  }))
})
