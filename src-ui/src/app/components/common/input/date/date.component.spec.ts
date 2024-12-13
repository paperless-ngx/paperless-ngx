import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { RouterTestingModule } from '@angular/router/testing'
import {
  NgbDateParserFormatter,
  NgbDatepickerModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { LocalizedDateParserFormatter } from 'src/app/utils/ngb-date-parser-formatter'
import { DateComponent } from './date.component'

describe('DateComponent', () => {
  let component: DateComponent
  let fixture: ComponentFixture<DateComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [DateComponent],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        NgbDatepickerModule,
        RouterTestingModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        {
          provide: NgbDateParserFormatter,
          useClass: LocalizedDateParserFormatter,
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(DateComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support use of input field', () => {
    input.value = '5/14/20'
    input.dispatchEvent(new Event('change'))
    fixture.detectChanges()
    expect(component.value).toEqual({ day: 14, month: 5, year: 2020 })
  })

  it('should use localzed placeholder from settings', () => {
    component.ngOnInit()
    expect(component.placeholder).toEqual('mm/dd/yyyy')
  })

  it('should support suggestions', () => {
    expect(component.value).toBeUndefined()
    component.suggestions = ['2023-05-31', '2014-05-14']
    fixture.detectChanges()
    const suggestionAnchor: HTMLAnchorElement =
      fixture.nativeElement.querySelector('a')
    suggestionAnchor.click()
    expect(component.value).toEqual({ day: 31, month: 5, year: 2023 })
  })

  it('should limit keyboard events', () => {
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

  it('should show allow system keyboard events', () => {
    let event: KeyboardEvent = new KeyboardEvent('keypress', {
      key: '9',
      altKey: true,
    })
    let preventDefaultSpy = jest.spyOn(event, 'preventDefault')
    input.dispatchEvent(event)
    expect(preventDefaultSpy).not.toHaveBeenCalled()
  })

  it('should support paste', () => {
    expect(component.value).toBeUndefined()
    const date = '5/4/20'
    const clipboardData = {
      dropEffect: null,
      effectAllowed: null,
      files: null,
      items: null,
      types: null,
      clearData: null,
      getData: () => date,
      setData: null,
      setDragImage: null,
    }
    const event = new Event('paste')
    event['clipboardData'] = clipboardData
    input.dispatchEvent(event)
    expect(component.value).toEqual({ day: 4, month: 5, year: 2020 })
    // coverage
    window['clipboardData'] = {
      getData: (type) => '',
    }
    component.onPaste(new Event('foo') as any)
  })

  it('should set filter button title', () => {
    component.title = 'foo'
    expect(component.filterButtonTitle).toEqual(
      'Filter documents with this foo'
    )
  })

  it('should emit date on filter', () => {
    let dateReceived
    component.value = '12/16/2023'
    component.filterDocuments.subscribe((date) => (dateReceived = date))
    component.onFilterDocuments()
    expect(dateReceived).toEqual([{ day: 16, month: 12, year: 2023 }])
  })
})
