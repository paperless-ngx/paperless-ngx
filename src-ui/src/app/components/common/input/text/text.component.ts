import { Component, Input, forwardRef } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
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
    SafeHtmlPipe,
    NgxBootstrapIconsModule,
  ],
})
export class TextComponent extends AbstractInputComponent<string> {
  @Input()
  autocomplete: string

  @Input()
  placeholder: string = ''

  constructor() {
    super()
  }
}
