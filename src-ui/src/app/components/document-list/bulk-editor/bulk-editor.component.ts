import { Component, EventEmitter, Input, Output } from '@angular/core';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';

@Component({
  selector: 'app-bulk-editor',
  templateUrl: './bulk-editor.component.html',
  styleUrls: ['./bulk-editor.component.scss']
})
export class BulkEditorComponent {

  @Input()
  list: DocumentListViewService

  @Output()
  selectPage = new EventEmitter()

  @Output()
  selectAll = new EventEmitter()

  @Output()
  selectNone = new EventEmitter()

  @Output()
  setCorrespondent = new EventEmitter()

  @Output()
  removeCorresponden = new EventEmitter()

  @Output()
  setDocumentType = new EventEmitter()

  @Output()
  removeDocumentType = new EventEmitter()

  @Output()
  addTag = new EventEmitter()

  @Output()
  removeTag = new EventEmitter()

  @Output()
  delete = new EventEmitter()

  constructor( ) { }

}
