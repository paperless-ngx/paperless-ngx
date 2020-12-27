import { Component, EventEmitter, Input, Output, OnInit } from '@angular/core';
import { MatchingModel } from 'src/app/data/matching-model';

export interface ToggleableItem {
  item: MatchingModel,
  state: ToggleableItemState,
  count: number
}

export enum ToggleableItemState {
  NotSelected = 0,
  Selected = 1,
  PartiallySelected = 2
}

@Component({
  selector: 'app-toggleable-dropdown-button',
  templateUrl: './toggleable-dropdown-button.component.html',
  styleUrls: ['./toggleable-dropdown-button.component.scss']
})
export class ToggleableDropdownButtonComponent {

  @Input()
  item: MatchingModel

  @Input()
  state: ToggleableItemState

  @Input()
  count: number

  @Output()
  toggle = new EventEmitter()

  get isTag(): boolean {
    return 'is_inbox_tag' in this.item
  }

  toggleItem(): void {
    this.toggle.emit()
  }

  getSelectedIconName() {
    if (this.state == ToggleableItemState.Selected) {
      return "check"
    } else if (this.state == ToggleableItemState.PartiallySelected) {
      return "dash"
    } else {
      return ""
    }
  }
}
