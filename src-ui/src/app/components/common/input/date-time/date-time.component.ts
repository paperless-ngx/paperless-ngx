import { formatDate } from '@angular/common';
import { Component, forwardRef, Input, OnInit } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => DateTimeComponent),
    multi: true
  }],
  selector: 'app-input-date-time',
  templateUrl: './date-time.component.html',
  styleUrls: ['./date-time.component.scss']
})
export class DateTimeComponent implements OnInit,ControlValueAccessor  {

  constructor() {
  }

  onChange = (newValue: any) => {};
  
  onTouched = () => {};

  writeValue(newValue: any): void {
    this.dateValue = formatDate(newValue, 'yyyy-MM-dd', "en-US")
    this.timeValue = formatDate(newValue, 'HH:mm:ss', 'en-US')
  }
  registerOnChange(fn: any): void {
    this.onChange = fn;
  }
  registerOnTouched(fn: any): void {
    this.onTouched = fn;
  }
  setDisabledState?(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  @Input()
  titleDate: string = "Date"

  @Input()
  titleTime: string

  @Input()
  disabled: boolean = false

  @Input()
  hint: string

  timeValue

  dateValue

  ngOnInit(): void {
  }

  dateOrTimeChanged() {
    this.onChange(formatDate(this.dateValue + "T" + this.timeValue,"yyyy-MM-ddTHH:mm:ssZZZZZ", "en-us", "UTC"))
  }

}
