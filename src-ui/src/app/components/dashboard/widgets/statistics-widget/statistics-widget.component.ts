import { DecimalPipe } from '@angular/common'
import { HttpClient } from '@angular/common/http'
import { Component, inject, OnDestroy, OnInit } from '@angular/core'
import { RouterModule } from '@angular/router'
import { NgbPopoverModule } from '@ng-bootstrap/ng-bootstrap'
import * as mimeTypeNames from 'mime-names'
import { first, Subject, Subscription, takeUntil } from 'rxjs'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import {
  FILTER_MIME_TYPE,
} from 'src/app/data/filter-rule-type'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { WebsocketStatusService } from 'src/app/services/websocket-status.service'
import { environment } from 'src/environments/environment'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'

export interface Statistics {
  documents_total?: number
  documents_inbox?: number
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

interface DonutSegment {
  mime_type: string
  name: string
  filetype: DocumentFileType
  color: string
  percent: number
  dasharray: string
  offset: number
}

// Gemini-style palette for donut slices (cool + warm mix)
const DONUT_PALETTE = [
  '#4285F4', // Blue
  '#34A853', // Green
  '#FBBC04', // Yellow
  '#EA4335', // Red
  '#A142F4', // Purple
  '#24C1E0', // Cyan
  '#FF7043', // Deep Orange
  '#9E9E9E', // Gray (for "Other")
]

@Component({
  selector: 'pngx-statistics-widget',
  templateUrl: './statistics-widget.component.html',
  styleUrls: ['./statistics-widget.component.scss'],
  imports: [WidgetFrameComponent, DecimalPipe, RouterModule],
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

  /** Which legend row the user is hovering (-1 = none) */
  hoveredIdx: number = -1

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
        const fileTypeMax = 6
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

  /** Compute SVG donut slices (circumference = 100 for ease) */
  donutSegments(): DonutSegment[] {
    const counts = this.statistics?.document_file_type_counts ?? []
    const total = counts.reduce((s, f) => s + f.mime_type_count, 0) || 1
    let cumulative = 25 // start at top (12 o'clock); for circle r=15.915 the top is offset -25
    const result: DonutSegment[] = []
    counts.forEach((ft, idx) => {
      const percent = (ft.mime_type_count / total) * 100
      // stroke-dasharray "<len> <gap>" — the visible portion is `percent`, the rest is gap
      const dasharray = `${percent} ${100 - percent}`
      // Negative offset rotates start to top, then accumulates
      const offset = -(cumulative - 25)
      result.push({
        mime_type: ft.mime_type,
        name: this.getFileTypeExtension(ft),
        filetype: ft,
        color: DONUT_PALETTE[idx % DONUT_PALETTE.length],
        percent,
        dasharray,
        offset,
      })
      cumulative += percent
    })
    return result
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