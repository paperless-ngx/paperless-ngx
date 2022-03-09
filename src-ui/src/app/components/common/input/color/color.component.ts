import { Component, Input, forwardRef } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { ColorEvent, ColorMode } from 'ngx-color';
import { randomColor, hslToHex } from 'src/app/utils/color';
import { AbstractInputComponent } from '../abstract-input';

@Component({
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => ColorComponent),
    multi: true
  }],
  selector: 'app-input-color',
  templateUrl: './color.component.html',
  styleUrls: ['./color.component.scss']
})
export class ColorComponent extends AbstractInputComponent<string> {

  @Input()
  colorMode: ColorMode = ColorMode.HEX

  constructor() {
    super()
  }

  randomize() {
    const color = randomColor(this.colorMode)
    let colorHex = color
    if (this.colorMode == ColorMode.HSL) {
      const hsl = color.split(',')
      colorHex = hslToHex(+hsl[0], +hsl[1], +hsl[2])
    }
    this.value = colorHex
    this.onChange(color)
  }

  sliderChanged(colorEvent:ColorEvent) {
    this.value = colorEvent.color.hex
    this.onChange(colorEvent.color[this.colorMode].toString())
  }
}
