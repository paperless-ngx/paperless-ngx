import { DecimalPipe } from '@angular/common'
import { HttpClient } from '@angular/common/http'
import { Component, inject, OnDestroy, OnInit } from '@angular/core'
import { RouterModule } from '@angular/router'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import * as mimeTypeNames from 'mime-names'
import { first, Subject, Subscription, takeUntil } from 'rxjs'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import {
  FILTER_HAS_TAGS_ANY,
  FILTER_MIME_TYPE,
} from 'src/app/data/filter-rule-type'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { WebsocketStatusService } from 'src/app/services/websocket-status.service'
import { environment } from 'src/environments/environment'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'

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
  is_other?: boolean
}

@Component({
  selector: 'pngx-statistics-widget',
  templateUrl: './statistics-widget.component.html',
  styleUrls: ['./statistics-widget.component.scss'],
  imports: [
    WidgetFrameComponent,
    IfPermissionsDirective,
    NgbPopoverModule,
    DecimalPipe,
    RouterModule,
  ],
})
export class StatisticsWidgetComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  private http = inject(HttpClient)
  private websocketConnectionService = inject(WebsocketStatusService)
  private documentListViewService = inject(DocumentListViewService)

  loading: boolean = false

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
            is_other: true,
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
    this.subscription = this.websocketConnectionService
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

  filterByFileType(filetype: DocumentFileType) {
    if (filetype.is_other) return
    this.documentListViewService.quickFilter([
      {
        rule_type: FILTER_MIME_TYPE,
        value: filetype.mime_type,
      },
    ])
  }
}
