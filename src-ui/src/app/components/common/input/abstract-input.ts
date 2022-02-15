import { Directive, ElementRef, Input, OnInit, ViewChild } from '@angular/core';
import { ControlValueAccessor } from '@angular/forms';
import { v4 as uuidv4 } from 'uuid';

@Directive()
export class AbstractInputComponent<T> implements OnInit, ControlValueAccessor {

  @ViewChild("inputField")
  inputField: ElementRef

  constructor() { }

  onChange = (newValue: T) => {};

  onTouched = () => {};

  writeValue(newValue: any): void {
    this.value = newValue
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

  focus() {
    if (this.inputField && this.inputField.nativeElement) {
      this.inputField.nativeElement.focus()
    }
  }

  @Input()
  title: string

  @Input()
  disabled = false;

  @Input()
  error: string

  value: T

  ngOnInit(): void {
    this.inputId = uuidv4()
  }

  inputId: string

  @Input()
  hint: string
}
