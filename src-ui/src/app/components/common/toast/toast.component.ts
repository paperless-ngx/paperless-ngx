import { Clipboard } from '@angular/cdk/clipboard'
import { DatePipe, DecimalPipe } from '@angular/common'
import {
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  OnInit,
  Output,
  ViewChild,
  inject,
  signal,
} from '@angular/core'
import { takeUntilDestroyed } from '@angular/core/rxjs-interop'
import {
  NgbProgressbarModule,
  NgbToast,
  NgbToastModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription, interval, takeWhile } from 'rxjs'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { Toast, ToastLevel } from 'src/app/services/toast.service'

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
  providers: [DatePipe, CustomDatePipe],
})
export class ToastComponent implements OnInit {
  private clipboard = inject(Clipboard)
  private customDatePipe = inject(CustomDatePipe)
  private destroyRef = inject(DestroyRef)
  readonly copied = signal(false)
  readonly ToastLevel = ToastLevel
  readonly delayRemaining = signal<number>(null)

  @ViewChild(NgbToast) ngbToast: NgbToast

  private hovered = false
  private focused = false
  private countdown: Subscription

  @Input() toast: Toast

  @Input() autohide: boolean = true

  /** Each new value re-renders the relative timestamp */
  @Input() now: Date

  @Output() hidden: EventEmitter<Toast> = new EventEmitter<Toast>()

  @Output() closed: EventEmitter<Toast> = new EventEmitter<Toast>()

  /** The toast's action button was clicked */
  @Output() actioned: EventEmitter<Toast> = new EventEmitter<Toast>()

  ngOnInit(): void {
    if (this.autohide) this.delayRemaining.set(this.toast.delay)
  }

  get relativeTimestamp(): string {
    return this.customDatePipe.transform(this.toast.timestamp, 'relative')
  }

  get paused(): boolean {
    return this.hovered || this.focused
  }

  setHovered(hovered: boolean) {
    this.hovered = hovered
  }

  setFocused(focused: boolean) {
    this.focused = focused
  }

  onShown(toast: Toast) {
    if (!this.autohide) return

    const refreshInterval = 150
    this.delayRemaining.set(toast.delay)

    this.countdown?.unsubscribe()
    this.countdown = interval(refreshInterval)
      .pipe(
        takeWhile(() => this.delayRemaining() > 0),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(() => {
        if (this.paused) return
        this.delayRemaining.update((remaining) =>
          Math.max(0, remaining - refreshInterval)
        )
        if (this.delayRemaining() === 0) {
          this.ngbToast?.hide()
        }
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
    this.copied.set(true)
    setTimeout(() => {
      this.copied.set(false)
    }, 3000)
  }

  getErrorText(error: any) {
    let text: string = error.error?.detail ?? error.error ?? ''
    if (typeof text === 'object') text = JSON.stringify(text)
    return `${text.slice(0, 200)}${text.length > 200 ? '...' : ''}`
  }
}
