import { Component, EventEmitter, forwardRef, Input, Output } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { AbstractInputComponent } from '../abstract-input';

@Component({
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => SelectComponent),
    multi: true
  }],
  selector: 'app-input-select',
  templateUrl: './select.component.html',
  styleUrls: ['./select.component.scss']
})
export class SelectComponent extends AbstractInputComponent<number> {

  constructor() {
    super()
    this.addItemRef = this.addItem.bind(this)
   }

  @Input()
  items: any[]

  @Input()
  textColor: any

  @Input()
  backgroundColor: any

  @Input()
  allowNull: boolean = false

  @Input()
  suggestions: number[]

  @Output()
  createNew = new EventEmitter<string>()

  public addItemRef: (name) => void

  private _lastSearchTerm: string

  get allowCreateNew(): boolean {
    return this.createNew.observers.length > 0
  }

  getSuggestions() {
    if (this.suggestions && this.items) {
      return this.suggestions.filter(id => id != this.value).map(id => this.items.find(item => item.id == id))
    } else {
      return []
    }
  }

  addItem(name: string) {
    if (name) this.createNew.next(name)
    else this.createNew.next(this._lastSearchTerm)
    this.clearLastSearchTerm()
  }

  clickNew() {
    this.createNew.next(this._lastSearchTerm)
    this.clearLastSearchTerm()
  }

  clearLastSearchTerm() {
    this._lastSearchTerm = null
  }

  onSearch($event) {
    this._lastSearchTerm = $event.term
  }

  onBlur() {
    setTimeout(() => {
      this.clearLastSearchTerm()
    }, 3000);
  }

}
