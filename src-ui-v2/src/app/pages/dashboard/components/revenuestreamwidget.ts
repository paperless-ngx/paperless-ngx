import { Component } from '@angular/core'
import { ChartModule } from 'primeng/chart'
import { debounceTime, Subscription } from 'rxjs'
import { LayoutService } from '../../../layout/service/layout.service'

@Component({
    standalone: true,
    selector: 'app-revenue-stream-widget',
    imports: [ChartModule],
    template: `<div class="card !mb-8">
        <div class="font-semibold text-xl mb-4">Revenue Stream</div>
        <p-chart type="bar" [data]="chartData" [options]="chartOptions" class="h-80" />
    </div>`,
})
export class RevenueStreamWidget {
    chartData: any

    chartOptions: any

    subscription!: Subscription

    constructor(public layoutService: LayoutService) {
        this.subscription = this.layoutService.configUpdate$.pipe(debounceTime(25)).subscribe(() => {
            this.initChart()
        })
    }

    ngOnInit() {
        this.initChart()
    }

    initChart() {
        const documentStyle = getComputedStyle(document.documentElement)
        const textColor = documentStyle.getPropertyValue('--text-color')
        const borderColor = documentStyle.getPropertyValue('--surface-border')
        const textMutedColor = documentStyle.getPropertyValue('--text-color-secondary')

        this.chartData = {
            labels: ['Q1', 'Q2', 'Q3', 'Q4'],
            datasets: [
                {
                    type: 'bar',
                    label: 'Subscriptions',
                    backgroundColor: documentStyle.getPropertyValue('--p-primary-400'),
                    data: [4000, 10000, 15000, 4000],
                    barThickness: 32,
                },
                {
                    type: 'bar',
                    label: 'Advertising',
                    backgroundColor: documentStyle.getPropertyValue('--p-primary-300'),
                    data: [2100, 8400, 2400, 7500],
                    barThickness: 32,
                },
                {
                    type: 'bar',
                    label: 'Affiliate',
                    backgroundColor: documentStyle.getPropertyValue('--p-primary-200'),
                    data: [4100, 5200, 3400, 7400],
                    borderRadius: {
                        topLeft: 8,
                        topRight: 8,
                        bottomLeft: 0,
                        bottomRight: 0,
                    },
                    borderSkipped: false,
                    barThickness: 32,
                },
            ],
        }

        this.chartOptions = {
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
                    stacked: true,
                    ticks: {
                        color: textMutedColor,
                    },
                    grid: {
                        color: 'transparent',
                        borderColor: 'transparent',
                    },
                },
                y: {
                    stacked: true,
                    ticks: {
                        color: textMutedColor,
                    },
                    grid: {
                        color: borderColor,
                        borderColor: 'transparent',
                        drawTicks: false,
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
