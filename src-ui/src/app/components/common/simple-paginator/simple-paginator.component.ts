import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'pngx-simple-paginator',
  templateUrl: './simple-paginator.component.html',
  styleUrls: ['./simple-paginator.component.scss']
})
export class SimplePaginatorComponent {
  // Two-way binding property: [(page)]
  @Input() page: number = 1;
  @Output() pageChange = new EventEmitter<number>();

  @Input() disablePrevious: boolean = false;
  @Input() disableNext: boolean = false;

  prevPage() {
    if (this.page > 1 && !this.disablePrevious) {
      this.pageChange.emit(this.page - 1);
    }
  }

  nextPage() {
    if (!this.disableNext) {
      this.pageChange.emit(this.page + 1);
    }
  }
}
