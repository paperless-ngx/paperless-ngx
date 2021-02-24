import { Component, forwardRef, Input, OnInit, ViewChild } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { NgbDateAdapter, NgbDateParserFormatter, NgbDatepickerContent } from '@ng-bootstrap/ng-bootstrap';
import { SettingsService } from 'src/app/services/settings.service';
import { v4 as uuidv4 } from 'uuid';
import { AbstractInputComponent } from '../abstract-input';


@Component({
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => DateComponent),
    multi: true
  }],
  selector: 'app-input-date',
  templateUrl: './date.component.html',
  styleUrls: ['./date.component.scss']
})
export class DateComponent extends AbstractInputComponent<string> implements OnInit {

  constructor(private settings: SettingsService) {
    super()
  }

  ngOnInit(): void {
    super.ngOnInit()
    this.placeholder = this.settings.getLocalizedDateInputFormat()
  }

  placeholder: string

}
