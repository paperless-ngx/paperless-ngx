import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { CurrencyPipe } from '@angular/common'
import { MonetaryComponent } from './monetary.component'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

describe('MonetaryComponent', () => {
  let component: MonetaryComponent
  let fixture: ComponentFixture<MonetaryComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [MonetaryComponent],
      imports: [FormsModule, ReactiveFormsModule],
      providers: [
        CurrencyPipe,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(MonetaryComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should set the currency code and monetary value correctly', () => {
    expect(component.currency).toEqual('USD') // default
    component.writeValue('G123.4')
    expect(component.currency).toEqual('G')

    component.writeValue('EUR123.4')
    expect(component.currency).toEqual('EUR')
    expect(component.monetaryValue).toEqual('123.40')
  })

  it('should set monetary value to fixed decimals', () => {
    component.monetaryValue = '10.5'
    component.monetaryValueChange(true)
    expect(component.monetaryValue).toEqual('10.50')
  })

  it('should set the default currency code based on LOCALE_ID', () => {
    expect(component.defaultCurrencyCode).toEqual('USD') // default
    component = new MonetaryComponent('pt-BR')
    expect(component.defaultCurrencyCode).toEqual('BRL')
  })

  it('should support setting a default currency code', () => {
    component.defaultCurrency = 'EUR'
    expect(component.defaultCurrencyCode).toEqual('EUR')
  })

  it('should parse monetary value correctly', () => {
    expect(component['parseMonetaryValue']('123.4')).toEqual('123.4')
    expect(component['parseMonetaryValue']('123.4', true)).toEqual('123.40')
    expect(component['parseMonetaryValue']('123.4', false)).toEqual('123.4')
  })

  it('should handle currency change', () => {
    component.writeValue('USD123.4')
    component.currency = 'EUR'
    component.currencyChange()
    expect(component.currency).toEqual('EUR')
    expect(component.monetaryValue).toEqual('123.40')
  })

  it('should handle monetary value change', () => {
    component.writeValue('USD123.4')
    component.monetaryValue = '123.4'
    component.monetaryValueChange()
    expect(component.monetaryValue).toEqual('123.4')
    expect(component.value).toEqual('USD123.40')
  })

  it('should handle null values', () => {
    component.writeValue(null)
    expect(component.currency).toEqual('USD')
    expect(component.monetaryValue).toEqual('')
  })

  it('should handle zero values', () => {
    component.writeValue('USD0.00')
    expect(component.currency).toEqual('USD')
    expect(component.monetaryValue).toEqual('0.00')
    component.monetaryValue = '0'
    component.monetaryValueChange()
    expect(component.value).toEqual('USD0.00')
  })
})
