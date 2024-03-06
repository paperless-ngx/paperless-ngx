import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { CurrencyPipe } from '@angular/common'
import { MonetaryComponent } from './monetary.component'

describe('MonetaryComponent', () => {
  let component: MonetaryComponent
  let fixture: ComponentFixture<MonetaryComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [MonetaryComponent],
      providers: [CurrencyPipe],
      imports: [FormsModule, ReactiveFormsModule, HttpClientTestingModule],
    }).compileComponents()

    fixture = TestBed.createComponent(MonetaryComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should set the currency code correctly', () => {
    expect(component.currencyCode).toEqual('USD') // default
    component.currencyCode = 'EUR'
    expect(component.currencyCode).toEqual('EUR')

    component.value = 'G123.4'
    jest
      .spyOn(document, 'activeElement', 'get')
      .mockReturnValue(component.currencyField.nativeElement)
    expect(component.currencyCode).toEqual('G')
  })

  it('should parse monetary value only when out of focus', () => {
    component.monetaryValue = 10.5
    jest.spyOn(document, 'activeElement', 'get').mockReturnValue(null)
    expect(component.monetaryValue).toEqual('10.50')

    component.value = 'GBP123.4'
    jest
      .spyOn(document, 'activeElement', 'get')
      .mockReturnValue(component.inputField.nativeElement)
    expect(component.monetaryValue).toEqual('123.4')
  })

  it('should report value including currency code and monetary value', () => {
    component.currencyCode = 'EUR'
    component.monetaryValue = 10.5
    expect(component.value).toEqual('EUR10.50')
  })

  it('should set the default currency code based on LOCALE_ID', () => {
    expect(component.defaultCurrencyCode).toEqual('USD') // default
    component = new MonetaryComponent('pt-BR')
    expect(component.defaultCurrencyCode).toEqual('BRL')
  })
})
