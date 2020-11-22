import { Component, Input, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { SavedViewConfig } from 'src/app/data/saved-view-config';
import { ConsumerStatusService } from 'src/app/services/consumer-status.service';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.scss']
})
export class SavedViewWidgetComponent implements OnInit {

  constructor(private documentService: DocumentService, private consumerStatusService: ConsumerStatusService) { }

  @Input()
  savedView: SavedViewConfig

  documents: PaperlessDocument[] = []

  subscription: Subscription

  ngOnInit(): void {
    this.reload()
    this.subscription = this.consumerStatusService.onDocumentConsumptionFinished().subscribe(status => {
      this.reload()
    })
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe()
  }

  reload() {
    this.documentService.list(1,10,this.savedView.sortField,this.savedView.sortDirection,this.savedView.filterRules).subscribe(result => {
      this.documents = result.results
    })
  }

}
