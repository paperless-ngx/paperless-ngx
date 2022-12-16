import {
  Directive,
  EventEmitter,
  HostBinding,
  HostListener,
  Input,
  Output,
} from '@angular/core'

export interface SortEvent {
  column: string
  reverse: boolean
}

@Directive({
  selector: 'th[appSortable]',
})
export class SortableDirective {
  constructor() {}

  @Input()
  appSortable: string = ''

  @Input()
  currentSortReverse: boolean = false

  @Input()
  currentSortField: string

  @Output() sort = new EventEmitter<SortEvent>()

  @HostBinding('class.asc') get asc() {
    return (
      this.currentSortField === this.appSortable && !this.currentSortReverse
    )
  }
  @HostBinding('class.des') get des() {
    return this.currentSortField === this.appSortable && this.currentSortReverse
  }

  @HostListener('click') rotate() {
    if (this.currentSortField != this.appSortable) {
      this.sort.emit({ column: this.appSortable, reverse: false })
    } else if (
      this.currentSortField == this.appSortable &&
      !this.currentSortReverse
    ) {
      this.sort.emit({ column: this.currentSortField, reverse: true })
    } else {
      this.sort.emit({ column: null, reverse: false })
    }
  }
}
