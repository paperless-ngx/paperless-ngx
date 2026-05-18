import { Component, Input, forwardRef } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { RouterLink } from '@angular/router'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => TextComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-text',
  templateUrl: './text.component.html',
  styleUrls: ['./text.component.scss'],
  imports: [
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
    RouterLink,
  ],
})
export class TextComponent extends AbstractInputComponent<string> {
  @Input()
  autocomplete: string

  @Input()
  placeholder: string = ''

  @Input()
  suggestion: string = ''

  constructor() {
    super()
  }

  getSuggestion() {
    return this.value !== this.suggestion ? this.suggestion : ''
  }

  applySuggestion() {
    this.value = this.suggestion
    this.onChange(this.value)
  }
}
