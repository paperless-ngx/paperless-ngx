import { Component, Input, OnInit } from '@angular/core';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-document-card-small',
  templateUrl: './document-card-small.component.html',
  styleUrls: ['./document-card-small.component.css']
})
export class DocumentCardSmallComponent implements OnInit {

  constructor(private documentService: DocumentService) { }

  @Input()
  document: PaperlessDocument

  ngOnInit(): void {
  }

  getThumbUrl() {
    return this.documentService.getThumbUrl(this.document.id)
  }

  getDownloadUrl() {
    return this.documentService.getDownloadUrl(this.document.id)
  }
}
