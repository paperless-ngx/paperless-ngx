import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
let fixture: ComponentFixture<DateDropdownComponent>
import {
  DateDropdownComponent,
  DateSelection,
  RelativeDate,
} from './date-dropdown.component'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { SettingsService } from 'src/app/services/settings.service'
import { ClearableBadgeComponent } from '../clearable-badge/clearable-badge.component'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DatePipe } from '@angular/common'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'

describe('DateDropdownComponent', () => {
  let component: DateDropdownComponent
  let settingsService: SettingsService
  let settingsSpy

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DateDropdownComponent,
        ClearableBadgeComponent,
        CustomDatePipe,
      ],
      providers: [SettingsService, CustomDatePipe, DatePipe],
      imports: [
        HttpClientTestingModule,
        NgbModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    settingsService = TestBed.inject(SettingsService)
    settingsSpy = jest.spyOn(settingsService, 'getLocalizedDateInputFormat')

    fixture = TestBed.createComponent(DateDropdownComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should use a localized date placeholder', () => {
    expect(component.datePlaceHolder).toEqual('mm/dd/yyyy')
    expect(settingsSpy).toHaveBeenCalled()
  })

  it('should support date input, emit change', fakeAsync(() => {
    let result: string
    component.dateAfterChange.subscribe((date) => (result = date))
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
    component.setRelativeDate(null)
    component.setRelativeDate(RelativeDate.LAST_7_DAYS)
    tick(500)
    expect(result).toEqual({
      after: null,
      before: null,
      relativeDateID: RelativeDate.LAST_7_DAYS,
    })
  }))

  it('should support report if active', () => {
    component.relativeDate = RelativeDate.LAST_7_DAYS
    expect(component.isActive).toBeTruthy()
    component.relativeDate = null
    component.dateAfter = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.dateAfter = null
    component.dateBefore = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.dateBefore = null
    expect(component.isActive).toBeFalsy()
  })

  it('should support reset', () => {
    component.dateAfter = '2023-05-30'
    component.reset()
    expect(component.dateAfter).toBeNull()
  })

  it('should support clearAfter', () => {
    component.dateAfter = '2023-05-30'
    component.clearAfter()
    expect(component.dateAfter).toBeNull()
  })

  it('should support clearBefore', () => {
    component.dateBefore = '2023-05-30'
    component.clearBefore()
    expect(component.dateBefore).toBeNull()
  })

  it('should limit keyboard events', () => {
    const input: HTMLInputElement = fixture.nativeElement.querySelector('input')
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
})
