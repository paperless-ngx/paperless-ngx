import { Component, forwardRef, Input, OnInit } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { v4 as uuidv4 } from 'uuid';
import { AbstractInputComponent } from '../abstract-input';

@Component({
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => SelectComponent),
    multi: true
  }],
  selector: 'app-input-select',
  templateUrl: './select.component.html',
  styleUrls: ['./select.component.css']
})
export class SelectComponent extends AbstractInputComponent<number> {

  constructor() {
    super()
   }

  @Input()
  items: any[]

  @Input()
  textColor: any

  @Input()
  backgroundColor: any

}
