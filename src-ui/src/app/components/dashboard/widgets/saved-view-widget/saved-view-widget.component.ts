import { Component, Input, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.scss']
})
export class SavedViewWidgetComponent implements OnInit {

  constructor(
    private documentService: DocumentService,
    private router: Router,
    private list: DocumentListViewService) { }
  
  @Input()
  savedView: PaperlessSavedView

  documents: PaperlessDocument[] = []

  ngOnInit(): void {
    this.documentService.listFiltered(1,10,this.savedView.sort_field, this.savedView.sort_reverse, this.savedView.filter_rules).subscribe(result => {
      this.documents = result.results
    })
  }

  showAll() {
    if (this.savedView.show_in_sidebar) {
      this.router.navigate(['view', this.savedView.id])
    } else {
      this.list.load(this.savedView)
      this.router.navigate(["documents"])
      }
  }

}
