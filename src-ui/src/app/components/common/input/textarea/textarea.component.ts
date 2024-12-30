import { Component, Input, forwardRef } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => TextAreaComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-textarea',
  templateUrl: './textarea.component.html',
  styleUrls: ['./textarea.component.scss'],
  imports: [FormsModule, ReactiveFormsModule, SafeHtmlPipe],
})
export class TextAreaComponent extends AbstractInputComponent<string> {
  @Input()
  placeholder: string = ''

  @Input()
  monospace: boolean = false

  constructor() {
    super()
  }
}
