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
  selector: 'th[pngxSortable]',
})
export class SortableDirective {
  constructor() {}

  @Input()
  pngxSortable: string = ''

  @Input()
  currentSortReverse: boolean = false

  @Input()
  currentSortField: string

  @Output() sort = new EventEmitter<SortEvent>()

  @HostBinding('class.asc') get asc() {
    return (
      this.currentSortField === this.pngxSortable && !this.currentSortReverse
    )
  }
  @HostBinding('class.des') get des() {
    return (
      this.currentSortField === this.pngxSortable && this.currentSortReverse
    )
  }

  @HostListener('click') rotate() {
    if (this.currentSortField != this.pngxSortable) {
      this.sort.emit({ column: this.pngxSortable, reverse: false })
    } else if (
      this.currentSortField == this.pngxSortable &&
      !this.currentSortReverse
    ) {
      this.sort.emit({ column: this.currentSortField, reverse: true })
    } else {
      this.sort.emit({ column: null, reverse: false })
    }
  }
}
