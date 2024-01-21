import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NumberComponent } from './number.component'
import { DocumentService } from 'src/app/services/rest/document.service'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { of } from 'rxjs'

describe('NumberComponent', () => {
  let component: NumberComponent
  let fixture: ComponentFixture<NumberComponent>
  let input: HTMLInputElement
  let documentService: DocumentService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [NumberComponent],
      providers: [DocumentService],
      imports: [FormsModule, ReactiveFormsModule, HttpClientTestingModule],
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

  it('should support float & monetary values', () => {
    component.writeValue(11.13)
    expect(component.value).toEqual(11)
    component.step = 0.01
    component.writeValue(11.1)
    expect(component.value).toEqual('11.10')
    component.step = 0.1
    component.writeValue(12.3456)
    expect(component.value).toEqual(12.3456)
    // float (step = .1) doesn't force 2 decimals
    component.writeValue(11.1)
    expect(component.value).toEqual(11.1)
  })

  it('should support scientific notation', () => {
    component.writeValue(1.23456789e8)
    expect(component.value).toEqual(123456789)
  })
})
