import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { map } from 'rxjs/operators';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-document-card-small',
  templateUrl: './document-card-small.component.html',
  styleUrls: ['./document-card-small.component.scss']
})
export class DocumentCardSmallComponent implements OnInit {

  constructor(private documentService: DocumentService) { }

  _selected = false

  get selected() {
    return this._selected
  }

  @Input()
  set selected(value: boolean) {
    this._selected = value
    this.selectedChange.emit(value)
  }

  @Output()
  selectedChange = new EventEmitter<boolean>()

  @Input()
  document: PaperlessDocument

  @Output()
  clickTag = new EventEmitter<number>()

  @Output()
  clickCorrespondent = new EventEmitter<number>()

  moreTags: number = null

  ngOnInit(): void {
  }

  getThumbUrl() {
    return this.documentService.getThumbUrl(this.document.id)
  }

  getDownloadUrl() {
    return this.documentService.getDownloadUrl(this.document.id)
  }

  getPreviewUrl() {
    return this.documentService.getPreviewUrl(this.document.id)
  }

  getTagsLimited$() {
    return this.document.tags$.pipe(
      map(tags => {
        if (tags.length > 7) {
          this.moreTags = tags.length - 6
          return tags.slice(0, 6)
        } else {
          return tags
        }
      })
    )
  }

}
