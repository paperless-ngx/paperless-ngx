import { Directive, EventEmitter, Input, Output } from '@angular/core';

export interface SortEvent {
  column: string
  reverse: boolean
}

@Directive({
  selector: 'th[sortable]',
  host: {
    '[class.asc]': 'currentSortField == sortable && !currentSortReverse',
    '[class.des]': 'currentSortField == sortable && currentSortReverse',
    '(click)': 'rotate()'
  }
})
export class SortableDirective {

  constructor() { }

  @Input()
  sortable: string = '';

  @Input()
  currentSortReverse: boolean = false

  @Input()
  currentSortField: string

  @Output() sort = new EventEmitter<SortEvent>();

  rotate() {
    if (this.currentSortField != this.sortable) {
      this.sort.emit({column: this.sortable, reverse: false});
    } else if (this.currentSortField == this.sortable && !this.currentSortReverse) {
      this.sort.emit({column: this.currentSortField, reverse: true});
    } else {
      this.sort.emit({column: null, reverse: false});
    }
  }
}
