import { Component, Input, forwardRef } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SwitchComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-switch',
  templateUrl: './switch.component.html',
  styleUrls: ['./switch.component.scss'],
})
export class SwitchComponent extends AbstractInputComponent<boolean> {
  @Input()
  showUnsetNote: boolean = false

  constructor() {
    super()
  }

  get isUnset(): boolean {
    return this.value === null || this.value === undefined
  }
}
