import { Component, Input, OnDestroy, OnInit } from '@angular/core'
import { Router } from '@angular/router'
import { Subscription } from 'rxjs'
import { PaperlessDocument } from 'src/app/data/paperless-document'
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { PaperlessTag } from 'src/app/data/paperless-tag'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'

@Component({
  selector: 'app-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: ['./saved-view-widget.component.scss'],
})
export class SavedViewWidgetComponent implements OnInit, OnDestroy {
  loading: boolean = true

  constructor(
    private documentService: DocumentService,
    private router: Router,
    private list: DocumentListViewService,
    private consumerStatusService: ConsumerStatusService,
    public openDocumentsService: OpenDocumentsService
  ) {}

  @Input()
  savedView: PaperlessSavedView

  documents: PaperlessDocument[] = []

  subscription: Subscription

  ngOnInit(): void {
    this.reload()
    this.subscription = this.consumerStatusService
      .onDocumentConsumptionFinished()
      .subscribe((status) => {
        this.reload()
      })
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe()
  }

  reload() {
    this.loading = this.documents.length == 0
    this.documentService
      .listFiltered(
        1,
        10,
        this.savedView.sort_field,
        this.savedView.sort_reverse,
        this.savedView.filter_rules
      )
      .subscribe((result) => {
        this.loading = false
        this.documents = result.results
      })
  }

  showAll() {
    if (this.savedView.show_in_sidebar) {
      this.router.navigate(['view', this.savedView.id])
    } else {
      this.router.navigate(['documents'], {
        queryParams: { view: this.savedView.id },
      })
    }
  }

  clickTag(tag: PaperlessTag) {
    this.list.quickFilter([
      { rule_type: FILTER_HAS_TAGS_ALL, value: tag.id.toString() },
    ])
  }
}
