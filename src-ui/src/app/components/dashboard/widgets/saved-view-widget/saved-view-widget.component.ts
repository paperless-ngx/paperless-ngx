import { Component, Input, OnInit } from '@angular/core';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { SavedViewConfig } from 'src/app/data/saved-view-config';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.scss']
})
export class SavedViewWidgetComponent implements OnInit {

  constructor(private documentService: DocumentService) { }
  
  @Input()
  savedView: SavedViewConfig

  documents: PaperlessDocument[] = []

  ngOnInit(): void {
    this.documentService.list(1,10,this.savedView.sortField,this.savedView.sortDirection,this.savedView.filterRules).subscribe(result => {
      this.documents = result.results
    })
  }

}
