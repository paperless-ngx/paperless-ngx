import { Component, forwardRef, Input } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { DocumentService } from 'src/app/services/rest/document.service'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => NumberComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-number',
  templateUrl: './number.component.html',
  styleUrls: ['./number.component.scss'],
})
export class NumberComponent extends AbstractInputComponent<number> {
  @Input()
  showAdd: boolean = true

  @Input()
  step: number = 1

  constructor(private documentService: DocumentService) {
    super()
  }

  nextAsn() {
    if (this.value) {
      return
    }
    this.documentService.getNextAsn().subscribe((nextAsn) => {
      this.value = nextAsn
      this.onChange(this.value)
    })
  }

  registerOnChange(fn: any): void {
    this.onChange = (newValue: any) => {
      // number validation
      if (this.step === 1 && newValue?.toString().indexOf('e') === -1)
        newValue = parseInt(newValue, 10)
      if (this.step === 0.01) newValue = parseFloat(newValue).toFixed(2)
      fn(newValue)
    }
  }

  writeValue(newValue: any): void {
    // Allow monetary values to be displayed with 2 decimals
    if (this.step === 0.01) newValue = parseFloat(newValue).toFixed(2)
    super.writeValue(newValue)
  }
}
