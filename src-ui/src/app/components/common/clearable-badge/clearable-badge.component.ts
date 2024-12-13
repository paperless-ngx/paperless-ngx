import { Component, EventEmitter, Input, Output } from '@angular/core'

@Component({
  selector: 'pngx-clearable-badge',
  templateUrl: './clearable-badge.component.html',
  styleUrls: ['./clearable-badge.component.scss'],
})
export class ClearableBadgeComponent {
  constructor() {}

  @Input()
  number: number

  @Input()
  selected: boolean

  @Output()
  cleared: EventEmitter<boolean> = new EventEmitter()

  get active(): boolean {
    return this.selected || this.number > -1
  }

  get isNumbered(): boolean {
    return this.number > -1
  }

  onClick(event: PointerEvent) {
    this.cleared.emit(true)
    event.stopImmediatePropagation()
    event.preventDefault()
  }
}
