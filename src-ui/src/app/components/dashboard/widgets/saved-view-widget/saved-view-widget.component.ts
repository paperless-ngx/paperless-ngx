import { Component, Input, OnDestroy, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { ConsumerStatusService } from 'src/app/services/consumer-status.service';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.scss']
})
export class SavedViewWidgetComponent implements OnInit, OnDestroy {

  constructor(
    private documentService: DocumentService,
    private router: Router,
    private list: DocumentListViewService,
    private consumerStatusService: ConsumerStatusService) { }

  @Input()
  savedView: PaperlessSavedView

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
    this.documentService.listFiltered(1,10,this.savedView.sort_field, this.savedView.sort_reverse, this.savedView.filter_rules).subscribe(result => {
      this.documents = result.results
    })
  }

  showAll() {
    if (this.savedView.show_in_sidebar) {
      this.router.navigate(['view', this.savedView.id])
    } else {
      this.list.loadSavedView(this.savedView, true)
      this.router.navigate(["documents"])
    }
  }

}
