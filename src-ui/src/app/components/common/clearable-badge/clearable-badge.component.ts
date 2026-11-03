import { Component, computed, EventEmitter, input, Output } from '@angular/core'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'

@Component({
  selector: 'pngx-clearable-badge',
  templateUrl: './clearable-badge.component.html',
  styleUrls: ['./clearable-badge.component.scss'],
  imports: [BootstrapIconComponent],
})
export class ClearableBadgeComponent {
  readonly number = input<number>(undefined)
  readonly selected = input<boolean>(undefined)

  @Output()
  cleared: EventEmitter<boolean> = new EventEmitter()

  readonly active = computed(() => this.selected() || this.number() > -1)

  readonly isNumbered = computed(() => this.number() > -1)

  onClick(event: PointerEvent) {
    this.cleared.emit(true)
    event.stopImmediatePropagation()
    event.preventDefault()
  }
}
