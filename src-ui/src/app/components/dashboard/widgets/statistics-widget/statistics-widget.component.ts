import { HttpClient } from '@angular/common/http'
import { Component, OnDestroy, OnInit } from '@angular/core'
import { Observable, Subscription } from 'rxjs'
import {
  FILTER_HAS_TAGS_ALL,
  FILTER_IS_IN_INBOX,
} from 'src/app/data/filter-rule-type'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { environment } from 'src/environments/environment'

export interface Statistics {
  documents_total?: number
  documents_inbox?: number
  inbox_tag?: number
  document_file_type_counts?: DocumentFileType[]
  character_count?: number
}

interface DocumentFileType {
  mime_type: string
  mime_type_count: number
}

@Component({
  selector: 'app-statistics-widget',
  templateUrl: './statistics-widget.component.html',
  styleUrls: ['./statistics-widget.component.scss'],
})
export class StatisticsWidgetComponent implements OnInit, OnDestroy {
  loading: boolean = true

  constructor(
    private http: HttpClient,
    private consumerStatusService: ConsumerStatusService,
    private documentListViewService: DocumentListViewService
  ) {}

  statistics: Statistics = {}

  subscription: Subscription

  private getStatistics(): Observable<Statistics> {
    return this.http.get(`${environment.apiBaseUrl}statistics/`)
  }

  reload() {
    this.loading = true
    this.getStatistics().subscribe((statistics) => {
      this.loading = false
      // truncate the list and sum others
      if (statistics.document_file_type_counts?.length > 4) {
        let others = statistics.document_file_type_counts.slice(4)
        statistics.document_file_type_counts =
          statistics.document_file_type_counts.slice(0, 4)
        statistics.document_file_type_counts.push({
          mime_type: $localize`other`,
          mime_type_count: others.reduce(
            (currentValue, documentFileType) =>
              documentFileType.mime_type_count + currentValue,
            0
          ),
        })
      }
      this.statistics = statistics
    })
  }

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

  goToInbox() {
    this.documentListViewService.quickFilter([
      {
        rule_type: FILTER_HAS_TAGS_ALL,
        value: this.statistics.inbox_tag.toString(),
      },
    ])
  }

  getFileTypePercent(filetype: DocumentFileType): number {
    return (filetype.mime_type_count / this.statistics?.documents_total) * 100
  }
}
