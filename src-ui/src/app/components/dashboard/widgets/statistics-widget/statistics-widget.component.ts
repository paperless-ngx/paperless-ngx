import { HttpClient } from '@angular/common/http'
import { Component, OnDestroy, OnInit } from '@angular/core'
import { first, Observable, Subject, Subscription, takeUntil } from 'rxjs'
import { FILTER_HAS_TAGS_ANY } from 'src/app/data/filter-rule-type'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { environment } from 'src/environments/environment'
import * as mimeTypeNames from 'mime-names'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'

export interface Statistics {
  documents_total?: number
  documents_inbox?: number
  inbox_tags?: number[]
  document_file_type_counts?: DocumentFileType[]
  character_count?: number
  tag_count?: number
  correspondent_count?: number
  document_type_count?: number
  storage_path_count?: number
  current_asn?: number
}

interface DocumentFileType {
  mime_type: string
  mime_type_count: number
}

@Component({
  selector: 'pngx-statistics-widget',
  templateUrl: './statistics-widget.component.html',
  styleUrls: ['./statistics-widget.component.scss'],
})
export class StatisticsWidgetComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  loading: boolean = false

  constructor(
    private http: HttpClient,
    private consumerStatusService: ConsumerStatusService,
    private documentListViewService: DocumentListViewService
  ) {
    super()
  }

  statistics: Statistics = {}

  subscription: Subscription
  private unsubscribeNotifer: Subject<any> = new Subject()

  reload() {
    if (this.loading) return
    this.loading = true
    this.http
      .get<Statistics>(`${environment.apiBaseUrl}statistics/`)
      .pipe(takeUntil(this.unsubscribeNotifer), first())
      .subscribe((statistics) => {
        this.loading = false
        const fileTypeMax = 5
        if (statistics.document_file_type_counts?.length > fileTypeMax) {
          const others = statistics.document_file_type_counts.slice(fileTypeMax)
          statistics.document_file_type_counts =
            statistics.document_file_type_counts.slice(0, fileTypeMax)
          statistics.document_file_type_counts.push({
            mime_type: $localize`Other`,
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

  getFileTypeExtension(filetype: DocumentFileType): string {
    return (
      mimeTypeNames[filetype.mime_type]?.extensions[0]?.toUpperCase() ??
      filetype.mime_type
    )
  }

  getFileTypeName(filetype: DocumentFileType): string {
    return mimeTypeNames[filetype.mime_type]?.name ?? filetype.mime_type
  }

  getFileTypePercent(filetype: DocumentFileType): number {
    return (filetype.mime_type_count / this.statistics?.documents_total) * 100
  }

  getItemOpacity(i: number): number {
    return 1 - i / this.statistics?.document_file_type_counts.length
  }

  ngOnInit(): void {
    this.reload()
    this.subscription = this.consumerStatusService
      .onDocumentConsumptionFinished()
      .subscribe(() => {
        this.reload()
      })
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe()
    this.unsubscribeNotifer.next(true)
    this.unsubscribeNotifer.complete()
  }

  goToInbox() {
    this.documentListViewService.quickFilter([
      {
        rule_type: FILTER_HAS_TAGS_ANY,
        value: this.statistics.inbox_tags
          .map((tagID) => tagID.toString())
          .join(','),
      },
    ])
  }
}
