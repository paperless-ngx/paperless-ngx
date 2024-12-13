import { Clipboard } from '@angular/cdk/clipboard'
import { Component, OnDestroy, OnInit } from '@angular/core'
import { Subscription, interval, take } from 'rxjs'
import { Toast, ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-toasts',
  templateUrl: './toasts.component.html',
  styleUrls: ['./toasts.component.scss'],
})
export class ToastsComponent implements OnInit, OnDestroy {
  constructor(
    public toastService: ToastService,
    private clipboard: Clipboard
  ) {}

  private subscription: Subscription

  public toasts: Toast[] = []

  public copied: boolean = false

  public seconds: number = 0

  ngOnDestroy(): void {
    this.subscription?.unsubscribe()
  }

  ngOnInit(): void {
    this.subscription = this.toastService.getToasts().subscribe((toasts) => {
      this.toasts = toasts
      this.toasts.forEach((t) => {
        if (typeof t.error === 'string') {
          try {
            t.error = JSON.parse(t.error)
          } catch (e) {}
        }
      })
    })
  }

  onShow(toast: Toast) {
    const refreshInterval = 150
    const delay = toast.delay - 500 // for fade animation

    interval(refreshInterval)
      .pipe(take(delay / refreshInterval))
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
