import { CommonModule } from '@angular/common'
import { Component } from '@angular/core'
import { ChartModule } from 'primeng/chart'
import { FluidModule } from 'primeng/fluid'
import { debounceTime, Subscription } from 'rxjs'
import { LayoutService } from '../../layout/service/layout.service'

@Component({
    selector: 'app-chart-demo',
    standalone: true,
    imports: [CommonModule, ChartModule, FluidModule],
    template: `
        <p-fluid class="grid grid-cols-12 gap-8">
            <div class="col-span-12 xl:col-span-6">
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Linear</div>
                    <p-chart type="line" [data]="lineData" [options]="lineOptions"></p-chart>
                </div>
            </div>
            <div class="col-span-12 xl:col-span-6">
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Bar</div>
                    <p-chart type="bar" [data]="barData" [options]="barOptions"></p-chart>
                </div>
            </div>
            <div class="col-span-12 xl:col-span-6">
                <div class="card flex flex-col items-center">
                    <div class="font-semibold text-xl mb-4">Pie</div>
                    <p-chart type="pie" [data]="pieData" [options]="pieOptions"></p-chart>
                </div>
            </div>
            <div class="col-span-12 xl:col-span-6">
                <div class="card flex flex-col items-center">
                    <div class="font-semibold text-xl mb-4">Doughnut</div>
                    <p-chart type="doughnut" [data]="pieData" [options]="pieOptions"></p-chart>
                </div>
            </div>
            <div class="col-span-12 xl:col-span-6">
                <div class="card flex flex-col items-center">
                    <div class="font-semibold text-xl mb-4">Polar Area</div>
                    <p-chart type="polarArea" [data]="polarData" [options]="polarOptions"></p-chart>
                </div>
            </div>
            <div class="col-span-12 xl:col-span-6">
                <div class="card flex flex-col items-center">
                    <div class="font-semibold text-xl mb-4">Radar</div>
                    <p-chart type="radar" [data]="radarData" [options]="radarOptions"></p-chart>
                </div>
            </div>
        </p-fluid>
    `,
})
export class ChartDemo {
    lineData: any

    barData: any

    pieData: any

    polarData: any

    radarData: any

    lineOptions: any

    barOptions: any

    pieOptions: any

    polarOptions: any

    radarOptions: any

    subscription: Subscription

    constructor(private layoutService: LayoutService) {
        this.subscription = this.layoutService.configUpdate$.pipe(debounceTime(25)).subscribe(() => {
            this.initCharts()
        })
    }

    ngOnInit() {
        this.initCharts()
    }

    initCharts() {
        const documentStyle = getComputedStyle(document.documentElement)
        const textColor = documentStyle.getPropertyValue('--text-color')
        const textColorSecondary = documentStyle.getPropertyValue('--text-color-secondary')
        const surfaceBorder = documentStyle.getPropertyValue('--surface-border')

        this.barData = {
            labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'],
            datasets: [
                {
                    label: 'My First dataset',
                    backgroundColor: documentStyle.getPropertyValue('--p-primary-500'),
                    borderColor: documentStyle.getPropertyValue('--p-primary-500'),
                    data: [65, 59, 80, 81, 56, 55, 40],
                },
                {
                    label: 'My Second dataset',
                    backgroundColor: documentStyle.getPropertyValue('--p-primary-200'),
                    borderColor: documentStyle.getPropertyValue('--p-primary-200'),
                    data: [28, 48, 40, 19, 86, 27, 90],
                },
            ],
        }

        this.barOptions = {
            maintainAspectRatio: false,
            aspectRatio: 0.8,
            plugins: {
                legend: {
                    labels: {
                        color: textColor,
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        color: textColorSecondary,
                        font: {
                            weight: 500,
                        },
                    },
                    grid: {
                        display: false,
                        drawBorder: false,
                    },
                },
                y: {
                    ticks: {
                        color: textColorSecondary,
                    },
                    grid: {
                        color: surfaceBorder,
                        drawBorder: false,
                    },
                },
            },
        }

        this.pieData = {
            labels: ['A', 'B', 'C'],
            datasets: [
                {
                    data: [540, 325, 702],
                    backgroundColor: [documentStyle.getPropertyValue('--p-indigo-500'), documentStyle.getPropertyValue('--p-purple-500'), documentStyle.getPropertyValue('--p-teal-500')],
                    hoverBackgroundColor: [documentStyle.getPropertyValue('--p-indigo-400'), documentStyle.getPropertyValue('--p-purple-400'), documentStyle.getPropertyValue('--p-teal-400')],
                },
            ],
        }

        this.pieOptions = {
            plugins: {
                legend: {
                    labels: {
                        usePointStyle: true,
                        color: textColor,
                    },
                },
            },
        }

        this.lineData = {
            labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'],
            datasets: [
                {
                    label: 'First Dataset',
                    data: [65, 59, 80, 81, 56, 55, 40],
                    fill: false,
                    backgroundColor: documentStyle.getPropertyValue('--p-primary-500'),
                    borderColor: documentStyle.getPropertyValue('--p-primary-500'),
                    tension: 0.4,
                },
                {
                    label: 'Second Dataset',
                    data: [28, 48, 40, 19, 86, 27, 90],
                    fill: false,
                    backgroundColor: documentStyle.getPropertyValue('--p-primary-200'),
                    borderColor: documentStyle.getPropertyValue('--p-primary-200'),
                    tension: 0.4,
                },
            ],
        }

        this.lineOptions = {
            maintainAspectRatio: false,
            aspectRatio: 0.8,
            plugins: {
                legend: {
                    labels: {
                        color: textColor,
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        color: textColorSecondary,
                    },
                    grid: {
                        color: surfaceBorder,
                        drawBorder: false,
                    },
                },
                y: {
                    ticks: {
                        color: textColorSecondary,
                    },
                    grid: {
                        color: surfaceBorder,
                        drawBorder: false,
                    },
                },
            },
        }

        this.polarData = {
            datasets: [
                {
                    data: [11, 16, 7, 3],
                    backgroundColor: [documentStyle.getPropertyValue('--p-indigo-500'), documentStyle.getPropertyValue('--p-purple-500'), documentStyle.getPropertyValue('--p-teal-500'), documentStyle.getPropertyValue('--p-orange-500')],
                    label: 'My dataset',
                },
            ],
            labels: ['Indigo', 'Purple', 'Teal', 'Orange'],
        }

        this.polarOptions = {
            plugins: {
                legend: {
                    labels: {
                        color: textColor,
                    },
                },
            },
            scales: {
                r: {
                    grid: {
                        color: surfaceBorder,
                    },
                    ticks: {
                        display: false,
                        color: textColorSecondary,
                    },
                },
            },
        }

        this.radarData = {
            labels: ['Eating', 'Drinking', 'Sleeping', 'Designing', 'Coding', 'Cycling', 'Running'],
            datasets: [
                {
                    label: 'My First dataset',
                    borderColor: documentStyle.getPropertyValue('--p-indigo-400'),
                    pointBackgroundColor: documentStyle.getPropertyValue('--p-indigo-400'),
                    pointBorderColor: documentStyle.getPropertyValue('--p-indigo-400'),
                    pointHoverBackgroundColor: textColor,
                    pointHoverBorderColor: documentStyle.getPropertyValue('--p-indigo-400'),
                    data: [65, 59, 90, 81, 56, 55, 40],
                },
                {
                    label: 'My Second dataset',
                    borderColor: documentStyle.getPropertyValue('--p-purple-400'),
                    pointBackgroundColor: documentStyle.getPropertyValue('--p-purple-400'),
                    pointBorderColor: documentStyle.getPropertyValue('--p-purple-400'),
                    pointHoverBackgroundColor: textColor,
                    pointHoverBorderColor: documentStyle.getPropertyValue('--p-purple-400'),
                    data: [28, 48, 40, 19, 96, 27, 100],
                },
            ],
        }

        this.radarOptions = {
            plugins: {
                legend: {
                    labels: {
                        color: textColor,
                    },
                },
            },
            scales: {
                r: {
                    pointLabels: {
                        color: textColor,
                    },
                    grid: {
                        color: surfaceBorder,
                    },
                },
            },
        }
    }

    ngOnDestroy() {
        if (this.subscription) {
            this.subscription.unsubscribe()
        }
    }
}
