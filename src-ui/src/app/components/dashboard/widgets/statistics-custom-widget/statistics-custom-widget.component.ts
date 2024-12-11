import { HttpClient, HttpParams } from '@angular/common/http'
import { Component, inject, OnDestroy, OnInit } from '@angular/core'
import { Observable, Subscription } from 'rxjs'
import { FILTER_HAS_TAGS_ALL } from 'src/app/data/filter-rule-type'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { environment } from 'src/environments/environment'

import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import Chart from 'chart.js/auto';
import ChartDataLabels from 'chartjs-plugin-datalabels';

import { NgbCalendar, NgbDate } from '@ng-bootstrap/ng-bootstrap'

Chart.register(ChartDataLabels)

export interface Statistics {
  labels_graph?: []
  data_graph?: []
  data_count_page_graph?: []
  data_document_type_pie_graph?: []
  labels_document_type_pie_graph?: []
  data_tags_pie_graph?: []
  labels_tags_pie_graph?: []
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

  calendar = inject(NgbCalendar)
  public documentCountChart: any
  public pageCountChart: any
  public documentTypePieChart: any
  public tagsPieChart: any
  statistics: Statistics = {}
  data_graph: []
  labels_graph: []
  data_count_page_graph: []
  data_document_type_pie_graph: []
  labels_document_type_pie_graph: []
  data_tags_pie_graph: []
  labels_tags_pie_graph: []
  fromDate: any
  toDate: any

  customDateEnable: boolean = true
  subscription: Subscription
  protected innitDate: string


  createDocumentCountBarChart() {
    if (this.documentCountChart) {
      this.documentCountChart.destroy()
    }
    this.documentCountChart = new Chart('DocumentChart',
      {
        type: 'bar',
        data: {
          labels: this.labels_graph,
          datasets: [{
            label: $localize`Documents`,
            data: this.data_graph,
            backgroundColor: [
              'rgba(75, 192, 192, 0.2)',
            ],
            borderColor: [
              'rgb(75, 192, 192)',
            ],
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          aspectRatio: 2.5,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                // Tùy chỉnh định dạng nhãn để hiển thị số nguyên
                callback: function(value, index, values) {
                  if (Number.isInteger(value)) {
                    return value
                  }
                  return null
                },
              },
            },
          },
          plugins: {
          datalabels: {
            display: false,
            // color: 'white',
          },
        },
        },
      },
    )
  }

  createCountPageBarChart() {
    if (this.pageCountChart) {
      this.pageCountChart.destroy()
    }
    this.pageCountChart = new Chart('CountPageChart',
      {
        type: 'bar',
        data: {
          labels: this.labels_graph,
          datasets: [{
            label: $localize`Pages`,
            data: this.data_count_page_graph,
            backgroundColor: [
              'rgba(255, 99, 132, 0.2)',
            ],
            borderColor: [
              'rgb(255, 99, 132)',
            ],
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          aspectRatio: 2.5,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                // Tùy chỉnh định dạng nhãn để hiển thị số nguyên
                callback: function(value, index, values) {
                  if (Number.isInteger(value)) {
                    return value
                  }
                  return null
                },
              },
            },
          },
          plugins: {
          datalabels: {
            display: false,
            // color: 'white',
          },
        },
        },
      },
    )
  }

  createDocumentTypePieChart() {
    if (this.documentTypePieChart) {
      return
    }
    this.documentTypePieChart = new Chart('DocumentTypePieChart', {
      type: 'doughnut', //this denotes tha type of chart

      data: {
        labels: this.labels_document_type_pie_graph,
        datasets: [{
          label: $localize`Document Type`,
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
            'rgb(135, 206, 235)',  // Sky Blue
          ],

          hoverOffset: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 2.5,
        cutout: '50%',
        plugins: {
          datalabels: {
            display: true,
            formatter: (value, ctx) => {
              const sum = ctx.dataset.data.reduce((a, b) => Number(a) + Number(b), 0)
              const percentage = ((value / Number(sum)) * 100).toFixed(2) + '%'
              return percentage
            },
            color: 'white',
          },
        },
      },

    })
  }

  createTagsPieChart() {
    if (this.tagsPieChart) {
      return
    }
    this.tagsPieChart = new Chart('TagsPieChart', {
      type: 'doughnut', //this denotes tha type of chart

      data: {
        labels: this.labels_tags_pie_graph,
        datasets: [{
          label: $localize`Tags`,
          data: this.data_tags_pie_graph,
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
            'rgb(135, 206, 235)',  // Sky Blue
          ],

          hoverOffset: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 2.5,
        cutout: '50%',
        plugins: {
          datalabels: {
            display: true,
            formatter: (value, ctx) => {
              const sum = ctx.dataset.data.reduce((a, b) => Number(a) + Number(b), 0)
              const percentage = ((value / Number(sum)) * 100).toFixed(2) + '%'
              return percentage
            },
            color: 'white',
          },
        },
      },

    })
  }

  private getStatistics(httpParams): Observable<Statistics> {
    return this.http.get(`${environment.apiBaseUrl}statistics_custom/`, { params: httpParams })
  }


  onDateRangeChange(event: { fromDate: any, toDate: any }) {
    this.fromDate = event.fromDate
    this.toDate = event.toDate
    if (this.fromDate && this.toDate)
      this.reload()

  }

  reload() {
    this.loading = true
    let httpParams = new HttpParams()
    if (this.fromDate && this.toDate) {
      httpParams = httpParams.set('from_date', this.fromDate)
      httpParams = httpParams.set('to_date', this.toDate)
    }

    this.getStatistics(httpParams).subscribe((statistics) => {
      this.loading = false
      this.statistics = statistics
      this.data_graph = statistics.data_graph
      this.data_count_page_graph = statistics.data_count_page_graph
      this.labels_graph = statistics.labels_graph
      this.data_document_type_pie_graph = statistics.data_document_type_pie_graph
      this.labels_document_type_pie_graph = statistics.labels_document_type_pie_graph
      this.data_tags_pie_graph = statistics.data_tags_pie_graph
      this.labels_tags_pie_graph = statistics.labels_tags_pie_graph
      this.createDocumentCountBarChart()
      this.createCountPageBarChart()
      this.createDocumentTypePieChart()
      this.createTagsPieChart()
    })
  }

  ngOnInit(): void {
    this.reload()
    // this.innitDate = this.convertNgbDateToString(this.calendar.getToday())
    // this.subscription = this.consumerStatusService
    //   .onDocumentConsumptionFinished()
    //   .subscribe(() => {
    //     this.reload()
    //   })
    // this.createBarChart()

  }

  ngOnDestroy(): void {
    // this.subscription.unsubscribe()
  }


  convertNgbDateToString(date: NgbDate): string {
    if (!date) {
      return ''
    }
    const year = date.year
    const month = date.month < 10 ? `0${date.month}` : date.month
    const day = date.day < 10 ? `0${date.day}` : date.day
    return `${year}-${month}-${day}`
  }

  onDateSelection(date: NgbDate) {
    this.fromDate = this.convertNgbDateToString(date)
    this.toDate = this.convertNgbDateToString(date)
    this.reload()
  }

}
