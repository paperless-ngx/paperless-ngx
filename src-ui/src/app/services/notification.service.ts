import { Injectable } from '@angular/core'
import { Subject } from 'rxjs'
import { v4 as uuidv4 } from 'uuid'

export interface Notification {
  id?: string

  content: string

  delay: number

  delayRemaining?: number

  action?: any

  actionName?: string

  classname?: string

  error?: any
}

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  constructor() {}
  _suppressPopupNotifications: boolean

  set suppressPopupNotifications(value: boolean) {
    this._suppressPopupNotifications = value
    this.showNotification.next(null)
  }

  private notifications: Notification[] = []

  private notificationsSubject: Subject<Notification[]> = new Subject()

  public showNotification: Subject<Notification> = new Subject()

  show(notification: Notification) {
    if (!notification.id) {
      notification.id = uuidv4()
    }
    if (typeof notification.error === 'string') {
      try {
        notification.error = JSON.parse(notification.error)
      } catch (e) {}
    }
    this.notifications.unshift(notification)
    if (!this._suppressPopupNotifications) {
      this.showNotification.next(notification)
    }
    this.notificationsSubject.next(this.notifications)
  }

  showError(content: string, error: any = null, delay: number = 10000) {
    this.show({
      content: content,
      delay: delay,
      classname: 'error',
      error,
    })
  }

  showInfo(content: string, delay: number = 5000) {
    this.show({ content: content, delay: delay })
  }

  closeNotification(notification: Notification) {
    let index = this.notifications.findIndex((t) => t.id == notification.id)
    if (index > -1) {
      this.notifications.splice(index, 1)
      this.notificationsSubject.next(this.notifications)
    }
  }

  getNotifications() {
    return this.notificationsSubject
  }

  clearNotifications() {
    this.notifications = []
    this.notificationsSubject.next(this.notifications)
    this.showNotification.next(null)
  }
}
