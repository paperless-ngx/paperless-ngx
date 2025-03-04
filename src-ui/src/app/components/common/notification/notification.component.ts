import { Clipboard } from '@angular/cdk/clipboard'
import { DecimalPipe } from '@angular/common'
import { Component, EventEmitter, Input, Output } from '@angular/core'
import {
  NgbProgressbarModule,
  NgbToastModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { interval, take } from 'rxjs'
import { Notification } from 'src/app/services/notification.service'

@Component({
  selector: 'pngx-notification',
  imports: [
    DecimalPipe,
    NgbToastModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
  templateUrl: './notification.component.html',
  styleUrl: './notification.component.scss',
})
export class NotificationComponent {
  @Input() notification: Notification

  @Input() autohide: boolean = true

  @Output() hidden: EventEmitter<Notification> =
    new EventEmitter<Notification>()

  @Output() close: EventEmitter<Notification> = new EventEmitter<Notification>()

  public copied: boolean = false

  constructor(private clipboard: Clipboard) {}

  onShown(notification: Notification) {
    if (!this.autohide) return

    const refreshInterval = 150
    const delay = notification.delay - 500 // for fade animation

    interval(refreshInterval)
      .pipe(take(Math.round(delay / refreshInterval)))
      .subscribe((count) => {
        notification.delayRemaining = Math.max(
          0,
          delay - refreshInterval * (count + 1)
        )
      })
  }

  public isDetailedError(error: any): boolean {
    return (
      typeof error === 'object' &&
      'status' in error &&
      'statusText' in error &&
      'url' in error &&
      'message' in error &&
      'error' in error
    )
  }

  public copyError(error: any) {
    this.clipboard.copy(JSON.stringify(error))
    this.copied = true
    setTimeout(() => {
      this.copied = false
    }, 3000)
  }

  getErrorText(error: any) {
    let text: string = error.error?.detail ?? error.error ?? ''
    if (typeof text === 'object') text = JSON.stringify(text)
    return `${text.slice(0, 200)}${text.length > 200 ? '...' : ''}`
  }
}
