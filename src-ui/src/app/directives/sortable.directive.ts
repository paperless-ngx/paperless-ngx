import { Directive, EventEmitter, Input, Output } from '@angular/core';

export interface SortEvent {
  column: string
  sorted: boolean
  reverse: boolean
}

@Directive({
  selector: 'th[sortable]',
  host: {
    '[class.asc]': 'sorted && !reverse',
    '[class.des]': 'sorted && reverse',
    '(click)': 'rotate()'
  }
})
export class SortableDirective {

  constructor() { }

  @Input()
  sortable: string = '';

  @Input()
  sorted: boolean = false

  @Input()
  reverse: boolean = false

  @Output() sort = new EventEmitter<SortEvent>();

  rotate() {
    if (!this.sorted) {
      this.sorted = true
      this.reverse = false
    } else if (this.sorted && !this.reverse) {
      this.reverse = true
    } else {
      this.sorted = false
    }
    this.sort.emit({column: this.sortable, sorted: this.sorted, reverse: this.reverse});
  }
}
