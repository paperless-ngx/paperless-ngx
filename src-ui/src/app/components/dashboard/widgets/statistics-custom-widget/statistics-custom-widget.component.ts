import { HttpClient, HttpParams } from '@angular/common/http'
import { Component, OnDestroy, OnInit } from '@angular/core'
import { Observable, Subscription } from 'rxjs'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { environment } from 'src/environments/environment'
import * as mimeTypeNames from 'mime-names'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import Chart from 'chart.js/auto'

export interface Statistics {
  labels_graph?: []
  data_graph?: []
  data_document_type_pie_graph?: []
  labels_document_type_pie_graph?: []
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
  implements OnInit, OnDestroy {
  loading: boolean = true

  constructor(
    private http: HttpClient,
    private consumerStatusService: ConsumerStatusService,
    private documentListViewService: DocumentListViewService,
  ) {
    super()
  }

  public chart: any
  public pieChart: any
  statistics: Statistics = {}
  data_graph: []
  labels_graph: []
  data_document_type_pie_graph: []
  labels_document_type_pie_graph: []

  subscription: Subscription

  createChart() {
    if (this.chart) {
      this.chart.destroy()
    }
    this.chart = new Chart('DocumentChart', {
      type: 'line', //this denotes tha type of chart

      data: {// values on X-Axis
        labels: this.labels_graph,
        datasets: [
          {
            label: 'Documents',
            data: this.data_graph,
            backgroundColor: 'rgb(75, 192, 192)',
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 2.5,
      },

    })
  }

  createPieChart() {
    if (this.pieChart) {
      this.pieChart.destroy()
    }
    this.pieChart = new Chart('DocumentTypePieChart', {
      type: 'doughnut', //this denotes tha type of chart

      data: {
        labels: this.labels_document_type_pie_graph,
        datasets: [{
          label: 'Document Type',
          data: this.data_document_type_pie_graph,
          backgroundColor: [
            'rgb(255, 99, 132)',  // Red
            'rgb(54, 162, 235)',  // Blue
            'rgb(255, 205, 86)',  // Yellow
            'rgb(75, 192, 192)',  // Teal
            'rgb(153, 102, 255)', // Purple
            'rgb(255, 159, 64)',  // Orange
            'rgb(199, 199, 199)', // Grey
            'rgb(255, 99, 71)',   // Tomato
            'rgb(144, 238, 144)', // Light Green
            'rgb(135, 206, 235)'  // Sky Blue
          ],

          hoverOffset: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 2.5,
      },

    })
  }

  private getStatistics(httpParams): Observable<Statistics> {
    return this.http.get(`${environment.apiBaseUrl}statistics_custom/`, { params: httpParams })
  }

  fromDate: any
  toDate: any
  dateRangePicker: boolean = false

  onDateRangeChange(event: { fromDate: any, toDate: any }) {
    this.fromDate = event.fromDate
    this.toDate = event.toDate
    if (!this.dateRangePicker) {
      this.dateRangePicker = true
      this.reload()
    }
  }

  reload() {
    this.loading = true
    let httpParams = new HttpParams()
    if (this.fromDate && this.toDate) {
      httpParams = httpParams.set('from_date', this.fromDate)
      httpParams = httpParams.set('to_date', this.toDate)
    }
    console.log('noi dung trong reload', this.fromDate, this.toDate)
    this.getStatistics(httpParams).subscribe((statistics) => {
      this.loading = false
      const fileTypeMax = 5

      this.statistics = statistics
      this.data_graph = statistics.data_graph
      this.labels_graph = statistics.labels_graph
      this.data_document_type_pie_graph = statistics.data_document_type_pie_graph
      this.labels_document_type_pie_graph = statistics.labels_document_type_pie_graph
      this.createChart()
      this.createPieChart()
    })
  }

  ngOnInit(): void {
    this.reload()
    this.subscription = this.consumerStatusService
      .onDocumentConsumptionFinished()
      .subscribe(() => {
        this.reload()
      })
    this.createChart()
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe()
  }

  confirmButton() {
    console.log("da goi ")
    this.reload()
  }
}
