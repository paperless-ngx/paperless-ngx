import { Component, EventEmitter, Input, Output } from '@angular/core'
import { MatchingModel } from 'src/app/data/matching-model'

export enum ToggleableItemState {
  NotSelected = 0,
  Selected = 1,
  PartiallySelected = 2,
  Excluded = 3,
}

@Component({
  selector: 'pngx-toggleable-dropdown-button',
  templateUrl: './toggleable-dropdown-button.component.html',
  styleUrls: ['./toggleable-dropdown-button.component.scss'],
})
export class ToggleableDropdownButtonComponent {
  @Input()
  item: MatchingModel

  @Input()
  state: ToggleableItemState

  @Input()
  count: number

  @Input()
  disabled: boolean = false

  @Input()
  hideCount: boolean = false

  @Input()
  opacifyCount: boolean = true

  @Output()
  toggled = new EventEmitter()

  @Output()
  exclude = new EventEmitter()

  get isTag(): boolean {
    return 'is_inbox_tag' in this.item
  }

  get currentCount(): number {
    return this.count ?? this.item.document_count
  }

  toggleItem(event: MouseEvent): void {
    if (this.state == ToggleableItemState.Selected) {
      this.exclude.emit()
    } else {
      this.toggled.emit()
    }
  }

  isChecked() {
    return this.state == ToggleableItemState.Selected
  }

  isPartiallyChecked() {
    return this.state == ToggleableItemState.PartiallySelected
  }

  isExcluded() {
    return this.state == ToggleableItemState.Excluded
  }
}
