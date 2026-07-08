import { Component, EventEmitter, Input, Output, signal } from '@angular/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'

@Component({
  selector: 'pngx-clearable-badge',
  templateUrl: './clearable-badge.component.html',
  styleUrls: ['./clearable-badge.component.scss'],
  imports: [NgxBootstrapIconsModule],
})
export class ClearableBadgeComponent {
  private numberSignal = signal<number>(undefined)
  private selectedSignal = signal<boolean>(undefined)

  @Input()
  get number(): number {
    return this.numberSignal()
  }

  set number(number: number) {
    this.numberSignal.set(number)
  }

  @Input()
  get selected(): boolean {
    return this.selectedSignal()
  }

  set selected(selected: boolean) {
    this.selectedSignal.set(selected)
  }

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
