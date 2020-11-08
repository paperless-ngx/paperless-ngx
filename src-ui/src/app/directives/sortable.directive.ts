import { Directive, EventEmitter, Input, Output } from '@angular/core';

export interface SortEvent {
  column: string;
  direction: string;
}

const rotate: {[key: string]: string} = { 'asc': 'des', 'des': '', '': 'asc' };

@Directive({
  selector: 'th[sortable]',
  host: {
    '[class.asc]': 'direction === "asc"',
    '[class.des]': 'direction === "des"',
    '(click)': 'rotate()'
  }
})
export class SortableDirective {

  constructor() { }

  @Input() sortable: string = '';
  @Input() direction: string = '';
  @Output() sort = new EventEmitter<SortEvent>();

  rotate() {
    this.direction = rotate[this.direction];
    this.sort.emit({column: this.sortable, direction: this.direction});
  }
}
