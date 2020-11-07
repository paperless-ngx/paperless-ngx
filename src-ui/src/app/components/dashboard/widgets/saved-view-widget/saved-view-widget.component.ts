import { Component, Input, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { SavedViewConfig } from 'src/app/data/saved-view-config';
import { ConsumerStatusService } from 'src/app/services/consumer-status.service';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.css']
})
export class SavedViewWidgetComponent implements OnInit, OnDestroy {

  constructor(private documentService: DocumentService, private consumerStatusService: ConsumerStatusService) { }

  @Input()
  viewConfig: SavedViewConfig

  documents: PaperlessDocument[]

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
    this.documentService.list(1,10,this.viewConfig.sortField,this.viewConfig.sortDirection,this.viewConfig.filterRules).subscribe(result => {
      this.documents = result.results
    })
  }

}
