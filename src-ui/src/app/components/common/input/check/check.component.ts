import { NgClass } from '@angular/common'
import { Component, forwardRef } from '@angular/core'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CheckComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-check',
  templateUrl: './check.component.html',
  styleUrls: ['./check.component.scss'],
  imports: [FormsModule, ReactiveFormsModule, NgClass, BootstrapIconComponent],
})
export class CheckComponent extends AbstractInputComponent<boolean> {
  constructor() {
    super()
  }
}
