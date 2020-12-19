import { Component, EventEmitter, Input, Output, OnInit } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { SelectableItem, SelectableItemState } from '../filterable-dropdown.component';

@Component({
  selector: 'app-filterable-dropdown-button',
  templateUrl: './filterable-dropdown-button.component.html',
  styleUrls: ['./filterable-dropdown-button.component.scss']
})
export class FilterableDropdownButtonComponent implements OnInit {

  @Input()
  selectableItem: SelectableItem

  get item(): PaperlessTag | PaperlessDocumentType | PaperlessCorrespondent {
    return this.selectableItem?.item
  }

  @Output()
  toggle = new EventEmitter()

  isTag: boolean

  ngOnInit() {
    this.isTag = 'is_inbox_tag' in this.item // ~ this.item instanceof PaperlessTag
  }

  toggleItem(): void {
    this.selectableItem.state = (this.selectableItem.state == SelectableItemState.NotSelected || this.selectableItem.state == SelectableItemState.PartiallySelected) ? SelectableItemState.Selected : SelectableItemState.NotSelected
    this.toggle.emit(this.selectableItem)
  }

  getSelectedIconName() {
    let iconName = ''
    if (this.selectableItem?.state == SelectableItemState.Selected) iconName = 'check'
    else if (this.selectableItem?.state == SelectableItemState.PartiallySelected) iconName = 'dash'
    return iconName
  }
}
