import { HttpClient } from '@angular/common/http'
import { Component, OnDestroy, OnInit } from '@angular/core'
import { Observable, Subscription } from 'rxjs'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { environment } from 'src/environments/environment'
import * as mimeTypeNames from 'mime-names'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import Chart from 'chart.js/auto';

export interface Statistics {
  documents_total?: number
  documents_inbox?: number
  inbox_tag?: number
  document_file_type_counts?: DocumentFileType[]
  character_count?: number
  tag_count?: number
  correspondent_count?: number
  document_type_count?: number
  storage_path_count?: number
  warehouse_count?: number
}

interface DocumentFileType {
  mime_type: string
  mime_type_count: number
}

@Component({
  selector: 'pngx-statistics-custom-widget',
  templateUrl: './statistics-custom-widget.component.html',
  styleUrls: ['./statistics-custom-widget.component.scss'],
})
export class StatisticsCustomWidgetComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  loading: boolean = true

  constructor(
    private http: HttpClient,
    private consumerStatusService: ConsumerStatusService,
    private documentListViewService: DocumentListViewService,
  ) {
    super()
  }
  public chart: any
  statistics: Statistics = {}

  subscription: Subscription

  createChart(){

    this.chart = new Chart("MyChart", {
      type: 'bar', //this denotes tha type of chart

      data: {// values on X-Axis
        labels: ['2022-05-10', '2022-05-11', '2022-05-12','2022-05-13',
                                 '2022-05-14', '2022-05-15', '2022-05-16','2022-05-17', ],
           datasets: [
          {
            label: "Sales",
            data: ['467','576', '572', '79', '92',
                                 '574', '573', '576'],
            backgroundColor: 'blue'
          },
          {
            label: "Profit",
            data: ['542', '542', '536', '327', '17',
                                     '0.00', '538', '541'],
            backgroundColor: 'limegreen'
          }
        ]
      },
      options: {
        aspectRatio:2.5
      }

    });
  }

  private getStatistics(): Observable<Statistics> {
    return this.http.get(`${environment.apiBaseUrl}statistics/`)
  }

  reload() {
    this.loading = true
    this.getStatistics().subscribe((statistics) => {
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
    this.createChart();
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
}
