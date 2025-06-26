import { CurrencyPipe, getLocaleCurrencyCode } from '@angular/common'
import { Component, forwardRef, inject, Input, LOCALE_ID } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => MonetaryComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-monetary',
  templateUrl: './monetary.component.html',
  styleUrls: ['./monetary.component.scss'],
  imports: [
    CurrencyPipe,
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
  ],
})
export class MonetaryComponent extends AbstractInputComponent<string> {
  currentLocale = inject(LOCALE_ID)

  public currency: string = ''

  public _monetaryValue: string = ''
  public get monetaryValue(): string {
    return this._monetaryValue
  }
  public set monetaryValue(value: any) {
    if (value || value?.toString() === '0')
      this._monetaryValue = value.toString()
  }

  defaultCurrencyCode: string

  @Input()
  set defaultCurrency(currency: string) {
    if (currency) this.defaultCurrencyCode = currency
  }

  constructor() {
    super()
    this.currency = this.defaultCurrencyCode =
      this.defaultCurrency ?? getLocaleCurrencyCode(this.currentLocale)
  }

  writeValue(newValue: any): void {
    this.currency = this.parseCurrencyCode(newValue)
    this.monetaryValue = this.parseMonetaryValue(newValue, true)

    this.value = this.currency + this.monetaryValue
  }

  public monetaryValueChange(fixed: boolean = false): void {
    this.monetaryValue = this.parseMonetaryValue(this.monetaryValue, fixed)
    if (this.monetaryValue === '0') {
      this.monetaryValue = '0.00'
    }
    this.onChange(this.currency + this.monetaryValue)
  }

  public currencyChange(): void {
    if (this.currency.length) {
      this.currency = this.parseCurrencyCode(this.currency)
      this.onChange(this.currency + this.monetaryValue?.toString())
    }
  }

  private parseCurrencyCode(value: string): string {
    return (
      value
        ?.toString()
        .toUpperCase()
        .match(/^([A-Z]{1,3})/)?.[0] ?? this.defaultCurrencyCode
    )
  }

  private parseMonetaryValue(value: string, fixed: boolean = false): string {
    if (!value) {
      return ''
    }
    const val: number = parseFloat(value.toString().replace(/[^0-9.,-]+/g, ''))
    return fixed ? val.toFixed(2) : val.toString()
  }
}
