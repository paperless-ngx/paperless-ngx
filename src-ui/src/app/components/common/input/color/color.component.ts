import { Component, forwardRef } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { randomColor } from 'src/app/utils/color'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => ColorComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-color',
  templateUrl: './color.component.html',
  styleUrls: ['./color.component.scss'],
})
export class ColorComponent extends AbstractInputComponent<string> {
  constructor() {
    super()
  }

  randomize() {
    this.colorChanged(randomColor())
  }

  colorChanged(value) {
    this.value = value
    this.onChange(value)
  }
}
