import { Component, forwardRef } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => UrlComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-url',
  templateUrl: './url.component.html',
  styleUrls: ['./url.component.scss'],
  imports: [NgxBootstrapIconsModule, FormsModule, ReactiveFormsModule],
})
export class UrlComponent extends AbstractInputComponent<string> {
  constructor() {
    super()
  }
}
