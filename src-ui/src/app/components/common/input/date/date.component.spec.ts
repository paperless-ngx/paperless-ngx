import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { DateComponent } from './date.component'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import {
  NgbDateParserFormatter,
  NgbDatepickerModule,
} from '@ng-bootstrap/ng-bootstrap'
import { RouterTestingModule } from '@angular/router/testing'
import { LocalizedDateParserFormatter } from 'src/app/utils/ngb-date-parser-formatter'

describe('DateComponent', () => {
  let component: DateComponent
  let fixture: ComponentFixture<DateComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [DateComponent],
      providers: [
        {
          provide: NgbDateParserFormatter,
          useClass: LocalizedDateParserFormatter,
        },
      ],
      imports: [
        FormsModule,
        ReactiveFormsModule,
        HttpClientTestingModule,
        NgbDatepickerModule,
        RouterTestingModule,
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
  })
})
