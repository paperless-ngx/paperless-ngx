import { Component, OnDestroy, OnInit } from '@angular/core'
import {
  NgbAccordionModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription } from 'rxjs'
import {
  Notification,
  NotificationService,
} from 'src/app/services/notification.service'
import { NotificationComponent } from '../notification/notification.component'

@Component({
  selector: 'pngx-notification-list',
  templateUrl: './notification-list.component.html',
  styleUrls: ['./notification-list.component.scss'],
  imports: [
    NotificationComponent,
    NgbAccordionModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
})
export class NotificationListComponent implements OnInit, OnDestroy {
  constructor(public notificationService: NotificationService) {}

  private subscription: Subscription

  public notifications: Notification[] = [] // array to force change detection

  ngOnDestroy(): void {
    this.subscription?.unsubscribe()
  }

  ngOnInit(): void {
    this.subscription = this.notificationService.showNotification.subscribe(
      (notification) => {
        this.notifications = notification ? [notification] : []
      }
    )
  }

  closeNotification() {
    this.notificationService.closeNotification(this.notifications[0])
    this.notifications = []
  }
}
