import { Component, Input, forwardRef } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { ColorEvent, ColorMode } from 'ngx-color';
import { randomColor } from 'src/app/utils/color';
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
    this.colorChanged(randomColor())
  }

  sliderChanged(colorEvent:ColorEvent) {
    this.colorChanged(colorEvent.color[this.colorMode].toString())
  }

  colorChanged(color:string) {
    this.value = color
    this.onChange(color)
  }
}
