import { Component, forwardRef } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import { ColorSliderModule } from 'ngx-color/slider'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
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
  imports: [
    BootstrapIconComponent,
    NgbPopoverModule,
    FormsModule,
    ReactiveFormsModule,
    ColorSliderModule,
  ],
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
