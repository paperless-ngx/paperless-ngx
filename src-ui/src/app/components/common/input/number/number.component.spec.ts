import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { of } from 'rxjs'
import { DocumentService } from 'src/app/services/rest/document.service'
import { NumberComponent } from './number.component'

describe('NumberComponent', () => {
  let component: NumberComponent
  let fixture: ComponentFixture<NumberComponent>
  let input: HTMLInputElement
  let documentService: DocumentService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [NumberComponent],
      imports: [FormsModule, ReactiveFormsModule],
      providers: [
        DocumentService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(NumberComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    documentService = TestBed.inject(DocumentService)
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support +1 ASN', () => {
    const nextAsnSpy = jest.spyOn(documentService, 'getNextAsn')
    nextAsnSpy.mockReturnValueOnce(of(1001)).mockReturnValueOnce(of(1))
    expect(component.value).toBeUndefined()
    component.nextAsn()
    expect(component.value).toEqual(1001)

    // this time results are empty
    component.value = undefined
    component.nextAsn()
    expect(component.value).toEqual(1)

    component.value = 1002
    component.nextAsn()
    expect(component.value).toEqual(1002)
  })

  it('should support float, monetary values & scientific notation', () => {
    const mockFn = jest.fn()
    component.registerOnChange(mockFn)

    component.step = 1
    component.onChange(11.13)
    expect(mockFn).toHaveBeenCalledWith(11)

    component.onChange(1.23456789e8)
    expect(mockFn).toHaveBeenCalledWith(123456789)

    component.step = 0.01
    component.onChange(11.1)
    expect(mockFn).toHaveBeenCalledWith('11.10')
  })

  it('should display monetary values fixed to 2 decimals', () => {
    component.step = 0.01
    component.writeValue(11.1)
    expect(component.value).toEqual('11.10')
  })
})
