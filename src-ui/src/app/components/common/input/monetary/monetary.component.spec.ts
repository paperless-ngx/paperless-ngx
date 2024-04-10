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
})
