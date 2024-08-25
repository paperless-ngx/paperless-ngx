import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
let fixture: ComponentFixture<DatesDropdownComponent>
import {
  DatesDropdownComponent,
  DateSelection,
  RelativeDate,
} from './dates-dropdown.component'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { SettingsService } from 'src/app/services/settings.service'
import { ClearableBadgeComponent } from '../clearable-badge/clearable-badge.component'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DatePipe } from '@angular/common'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

describe('DatesDropdownComponent', () => {
  let component: DatesDropdownComponent
  let settingsService: SettingsService
  let settingsSpy

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        DatesDropdownComponent,
        ClearableBadgeComponent,
        CustomDatePipe,
      ],
      imports: [
        NgbModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
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
    component.createdDateAfterChange.subscribe((date) => (result = date))
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
    component.setCreatedRelativeDate(null)
    component.setCreatedRelativeDate(RelativeDate.LAST_7_DAYS)
    component.setAddedRelativeDate(null)
    component.setAddedRelativeDate(RelativeDate.LAST_7_DAYS)
    tick(500)
    expect(result).toEqual({
      createdAfter: null,
      createdBefore: null,
      createdRelativeDateID: RelativeDate.LAST_7_DAYS,
      addedAfter: null,
      addedBefore: null,
      addedRelativeDateID: RelativeDate.LAST_7_DAYS,
    })
  }))

  it('should support report if active', () => {
    component.createdRelativeDate = RelativeDate.LAST_7_DAYS
    expect(component.isActive).toBeTruthy()
    component.createdRelativeDate = null
    component.createdDateAfter = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.createdDateAfter = null
    component.createdDateBefore = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.createdDateBefore = null

    component.addedRelativeDate = RelativeDate.LAST_7_DAYS
    expect(component.isActive).toBeTruthy()
    component.addedRelativeDate = null
    component.addedDateAfter = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.addedDateAfter = null
    component.addedDateBefore = '2023-05-30'
    expect(component.isActive).toBeTruthy()
    component.addedDateBefore = null

    expect(component.isActive).toBeFalsy()
  })

  it('should support reset', () => {
    component.createdDateAfter = '2023-05-30'
    component.reset()
    expect(component.createdDateAfter).toBeNull()
  })

  it('should support clearAfter', () => {
    component.createdDateAfter = '2023-05-30'
    component.clearCreatedAfter()
    expect(component.createdDateAfter).toBeNull()

    component.addedDateAfter = '2023-05-30'
    component.clearAddedAfter()
    expect(component.addedDateAfter).toBeNull()
  })

  it('should support clearBefore', () => {
    component.createdDateBefore = '2023-05-30'
    component.clearCreatedBefore()
    expect(component.createdDateBefore).toBeNull()

    component.addedDateBefore = '2023-05-30'
    component.clearAddedBefore()
    expect(component.addedDateBefore).toBeNull()
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
