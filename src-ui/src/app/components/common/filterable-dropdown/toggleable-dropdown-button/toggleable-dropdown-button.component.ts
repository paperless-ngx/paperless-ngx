import { Component, EventEmitter, Input, Output, OnInit } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';

export interface ToggleableItem {
  item: PaperlessTag | PaperlessDocumentType | PaperlessCorrespondent,
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

  @Input()
  showCounts: boolean = true

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
    let iconName = ''
    if (this.toggleableItem?.state == ToggleableItemState.Selected) iconName = 'check'
    else if (this.toggleableItem?.state == ToggleableItemState.PartiallySelected) iconName = 'dash'
    return iconName
  }
}
