import { Component } from '@angular/core'
import { NotificationsWidget } from './components/notificationswidget'
import { StatsWidget } from './components/statswidget'
import { RecentSalesWidget } from './components/recentsaleswidget'
import { BestSellingWidget } from './components/bestsellingwidget'
import { RevenueStreamWidget } from './components/revenuestreamwidget'

@Component({
    selector: 'app-dashboard',
    imports: [StatsWidget, RecentSalesWidget, BestSellingWidget, RevenueStreamWidget, NotificationsWidget],
    template: `
        <div class="grid grid-cols-12 gap-8">
            <!--          TODO: CẬP NHẬT GIAO DIỆN KHỞI TẠO Ở ĐÂY-->
        </div>
    `,
})
export class Dashboard {
}
