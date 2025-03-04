import { Component, OnDestroy, OnInit } from '@angular/core'
import {
  NgbDropdownModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription } from 'rxjs'
import {
  Notification,
  NotificationService,
} from 'src/app/services/notification.service'
import { NotificationComponent } from '../../common/notification/notification.component'

@Component({
  selector: 'pngx-notifications-dropdown',
  templateUrl: './notifications-dropdown.component.html',
  styleUrls: ['./notifications-dropdown.component.scss'],
  imports: [
    NotificationComponent,
    NgbDropdownModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
})
export class NotificationsDropdownComponent implements OnInit, OnDestroy {
  constructor(public notificationService: NotificationService) {}

  private subscription: Subscription

  public notifications: Notification[] = []

  ngOnDestroy(): void {
    this.subscription?.unsubscribe()
  }

  ngOnInit(): void {
    this.subscription = this.notificationService
      .getNotifications()
      .subscribe((notifications) => {
        this.notifications = [...notifications]
      })
  }

  onOpenChange(open: boolean): void {
    this.notificationService.suppressPopupNotifications = open
  }
}
