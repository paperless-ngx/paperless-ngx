import { Component, EventEmitter, Input, Output } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';

@Component({
  selector: 'app-filter-dropdown-button',
  templateUrl: './filter-dropdown-button.component.html',
  styleUrls: ['./filter-dropdown-button.component.scss']
})
export class FilterDropdownButtonComponent {

  constructor() { }

  @Input()
  item: PaperlessTag | PaperlessDocumentType | PaperlessCorrespondent

  @Input()
  display: string

  @Input()
  selected: boolean

  @Output()
  toggle = new EventEmitter()


  toggleItem(): void {
    this.selected = !this.selected
    this.toggle.emit(this.item)
  }
}
