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

  fileTypeDataArray = []

  private fileTypeColors = [
    '#e84118', // red
    '#00a8ff', // blue
    '#4cd137', // green
    '#9c88ff', // purple
    '#fbc531', // yellow
    '#7f8fa6', // gray
  ]

  reload() {
    this.loading = true
    this.getStatistics().subscribe((statistics) => {
      this.loading = false
      const fileTypeMax = 5
      if (statistics.document_file_type_counts?.length > fileTypeMax) {
        let others = statistics.document_file_type_counts.slice(fileTypeMax)
        statistics.document_file_type_counts =
          statistics.document_file_type_counts.slice(0, fileTypeMax)
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

      this.updateFileTypePercentages()
    })
  }

  private updateFileTypePercentages() {
    let colorIndex = 0
    this.fileTypeDataArray = this.statistics.document_file_type_counts.map(
      (fileType) => {
        const percentage =
          (fileType.mime_type_count / this.statistics?.documents_total) * 100
        return {
          name: this.getMimeTypeName(fileType.mime_type),
          percentage: percentage.toFixed(2),
          color: this.fileTypeColors[colorIndex++],
        }
      }
    )
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

  getMimeTypeName(mimeType: string): string {
    const mimeTypesMap: { [key: string]: string } = {
      'application/msword': 'Microsoft Word',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        'Microsoft Word',
      'application/vnd.ms-excel': 'Microsoft Excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        'Microsoft Excel',
      'application/vnd.ms-powerpoint': 'Microsoft PowerPoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation':
        'Microsoft PowerPoint',
      'application/pdf': 'PDF',
      'application/vnd.oasis.opendocument.text': 'OpenDocument Text',
      'application/vnd.oasis.opendocument.spreadsheet':
        'OpenDocument Spreadsheet',
      'application/vnd.oasis.opendocument.presentation':
        'OpenDocument Presentation',
      'application/vnd.oasis.opendocument.graphics': 'OpenDocument Graphics',
      'application/rtf': 'Rich Text Format',
      'text/plain': 'Plain Text',
      'text/csv': 'CSV',
      'image/jpeg': 'JPEG',
      'image/png': 'PNG',
      'image/gif': 'GIF',
      'image/svg+xml': 'SVG',
    }

    return mimeTypesMap[mimeType] || mimeType
  }
}
