import {
  Component,
  EventEmitter,
  forwardRef,
  Input,
  Output,
} from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SelectComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-select',
  templateUrl: './select.component.html',
  styleUrls: ['./select.component.scss'],
})
export class SelectComponent extends AbstractInputComponent<number> {
  constructor() {
    super()
    this.addItemRef = this.addItem.bind(this)
  }

  _items: any[]

  @Input()
  set items(items) {
    this._items = items
    if (items && this.value) this.checkForPrivateItems(this.value)
  }

  @Input()
  set itemsArray(items: any[]) {
    this._items = items.map((item, index) => ({ id: index, name: item }))
  }

  writeValue(newValue: any): void {
    if (newValue && this._items) {
      this.checkForPrivateItems(newValue)
      this.items = [...this._items] // we need to explicitly re-set items
    }
    super.writeValue(newValue)
  }

  checkForPrivateItems(value: any) {
    if (Array.isArray(value)) {
      if (value.length > 0) value.forEach((id) => this.checkForPrivateItem(id))
    } else {
      this.checkForPrivateItem(value)
    }
  }

  checkForPrivateItem(id) {
    if (this._items.find((i) => i.id === id) === undefined) {
      this._items.push({
        id: id,
        name: $localize`Private`,
        private: true,
      })
    }
  }

  get items(): any[] {
    return this._items
  }

  @Input()
  textColor: any

  @Input()
  backgroundColor: any

  @Input()
  allowNull: boolean = false

  @Input()
  suggestions: number[]

  @Input()
  placeholder: string

  @Input()
  multiple: boolean = false

  @Input()
  bindLabel: string = 'name'

  @Input()
  showFilter: boolean = false

  @Input()
  notFoundText: string = $localize`No items found`

  @Input()
  disableCreateNew: boolean = false

  @Input()
  hideAddButton: boolean = false

  @Output()
  createNew = new EventEmitter<string>()

  @Output()
  filterDocuments = new EventEmitter<any[]>()

  public addItemRef: (name) => void

  private _lastSearchTerm: string

  get allowCreateNew(): boolean {
    return !this.disableCreateNew && this.createNew.observers.length > 0
  }

  get isPrivate(): boolean {
    return this.items?.find((i) => i.id === this.value)?.private
  }

  getSuggestions() {
    if (this.suggestions && this.items) {
      return this.suggestions
        .filter((id) => id != this.value)
        .map((id) => this.items.find((item) => item.id == id))
    } else {
      return []
    }
  }

  addItem(name: string = null) {
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
    }, 3000)
  }

  onFilterDocuments() {
    this.filterDocuments.emit([this.items.find((i) => i.id === this.value)])
  }

  get filterButtonTitle() {
    return $localize`Filter documents with this ${this.title}`
  }
}
