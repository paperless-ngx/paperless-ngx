import { Component, Input, forwardRef } from '@angular/core'
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
  @Input()
  showReveal: boolean = false

  @Input()
  autocomplete: string

  public textVisible: boolean = false

  public toggleVisibility(): void {
    this.textVisible = !this.textVisible
  }

  public onFocus() {
    if (this.value?.replace(/\*/g, '').length === 0) {
      this.writeValue('')
    }
  }

  public onFocusOut() {
    if (this.value?.length === 0) {
      this.writeValue('**********')
      this.onChange(this.value)
    }
  }

  get disableRevealToggle(): boolean {
    return this.value?.replace(/\*/g, '').length === 0
  }
}
