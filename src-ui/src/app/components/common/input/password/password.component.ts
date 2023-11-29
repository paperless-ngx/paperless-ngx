import { Component, forwardRef } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PasswordComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-password',
  templateUrl: './password.component.html',
  styleUrls: ['./password.component.scss'],
})
export class PasswordComponent extends AbstractInputComponent<string> {
  constructor() {
    super()
  }
}
