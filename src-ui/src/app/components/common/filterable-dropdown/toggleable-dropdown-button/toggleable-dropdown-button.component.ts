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
  toggleableItem: ToggleableItem

  @Output()
  toggle = new EventEmitter()

  get isTag(): boolean {
    return 'is_inbox_tag' in this.toggleableItem?.item // ~ this.item instanceof PaperlessTag
  }

  toggleItem(): void {
    this.toggleableItem.state = (this.toggleableItem.state == ToggleableItemState.NotSelected || this.toggleableItem.state == ToggleableItemState.PartiallySelected) ? ToggleableItemState.Selected : ToggleableItemState.NotSelected
    this.toggle.emit(this.toggleableItem)
  }

  getSelectedIconName() {
    if (this.toggleableItem?.state == ToggleableItemState.Selected) {
      return "check"
    } else if (this.toggleableItem?.state == ToggleableItemState.PartiallySelected) {
      return "dash"
    } else {
      return ""
    }
  }
}
