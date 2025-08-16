import { Clipboard } from '@angular/cdk/clipboard'
import { DecimalPipe } from '@angular/common'
import { Component, EventEmitter, Input, Output, inject } from '@angular/core'
import {
  NgbProgressbarModule,
  NgbToastModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { interval, take } from 'rxjs'
import { Toast } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-toast',
  imports: [
    DecimalPipe,
    NgbToastModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
  templateUrl: './toast.component.html',
  styleUrl: './toast.component.scss',
})
export class ToastComponent {
  private clipboard = inject(Clipboard)

  @Input() toast: Toast

  @Input() autohide: boolean = true

  @Output() hidden: EventEmitter<Toast> = new EventEmitter<Toast>()

  @Output() closed: EventEmitter<Toast> = new EventEmitter<Toast>()

  public copied: boolean = false

  onShown(toast: Toast) {
    if (!this.autohide) return

    const refreshInterval = 150
    const delay = toast.delay - 500 // for fade animation

    interval(refreshInterval)
      .pipe(take(Math.round(delay / refreshInterval)))
      .subscribe((count) => {
        toast.delayRemaining = Math.max(
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
