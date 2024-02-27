import {
  Component,
  DEFAULT_CURRENCY_CODE,
  ElementRef,
  forwardRef,
  Inject,
  ViewChild,
} from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
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
})
export class MonetaryComponent extends AbstractInputComponent<string> {
  @ViewChild('currencyField')
  currencyField: ElementRef

  constructor(
    @Inject(DEFAULT_CURRENCY_CODE) public defaultCurrencyCode: string
  ) {
    super()
  }

  get currencyCode(): string {
    const focused = document.activeElement === this.currencyField?.nativeElement
    if (focused && this.value) return this.value.match(/^([A-Z]{0,3})/)?.[0]
    return (
      this.value
        ?.toString()
        .toUpperCase()
        .match(/^([A-Z]{1,3})/)?.[0] ?? this.defaultCurrencyCode
    )
  }

  set currencyCode(value: string) {
    this.value = value + this.monetaryValue?.toString()
  }

  get monetaryValue(): string {
    if (!this.value) return null
    const focused = document.activeElement === this.inputField?.nativeElement
    const val = parseFloat(this.value.toString().replace(/[^0-9.,]+/g, ''))
    return focused ? val.toString() : val.toFixed(2)
  }

  set monetaryValue(value: number) {
    this.value = this.currencyCode + value.toFixed(2)
  }
}
