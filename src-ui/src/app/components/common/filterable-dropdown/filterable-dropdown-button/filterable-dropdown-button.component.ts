import { Component, EventEmitter, Input, Output, OnInit } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { ToggleableItem, ToggleableItemState } from '../filterable-dropdown.component';

@Component({
  selector: 'app-filterable-dropdown-button',
  templateUrl: './filterable-dropdown-button.component.html',
  styleUrls: ['./filterable-dropdown-button.component.scss']
})
export class FilterableDropdownButtonComponent {

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
    let iconName = ''
    if (this.toggleableItem?.state == ToggleableItemState.Selected) iconName = 'check'
    else if (this.toggleableItem?.state == ToggleableItemState.PartiallySelected) iconName = 'dash'
    return iconName
  }
}
