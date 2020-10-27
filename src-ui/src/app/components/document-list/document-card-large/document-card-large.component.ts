import { Component, Input, OnInit } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { DocumentService } from 'src/app/services/rest/document.service';
import { SearchResultHighlightedText } from 'src/app/services/rest/search.service';

@Component({
  selector: 'app-document-card-large',
  templateUrl: './document-card-large.component.html',
  styleUrls: ['./document-card-large.component.css']
})
export class DocumentCardLargeComponent implements OnInit {

  constructor(private documentService: DocumentService, private sanitizer: DomSanitizer) { }

  @Input()
  document: PaperlessDocument

  @Input()
  details: any

  ngOnInit(): void {
  }

  getDetailsAsString() {
    if (typeof this.details === 'string') {
      return this.details.substring(0, 500)
    }
  }

  getDetailsAsHighlight() {
    //TODO: this is not an exact typecheck, can we do better
    if (this.details instanceof Array) {
      return this.details
    }
  }

  getThumbUrl() {
    return this.documentService.getThumbUrl(this.document.id)
  }

  getDownloadUrl() {
    return this.documentService.getDownloadUrl(this.document.id)
  }
}
