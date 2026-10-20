import {
  Component,
  DestroyRef,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core'
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop'
import {
  NgbDropdown,
  NgbDropdownModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription, interval, map } from 'rxjs'
import { Toast, ToastLevel, ToastService } from 'src/app/services/toast.service'
import { ToastComponent } from '../../common/toast/toast.component'

@Component({
  selector: 'pngx-toasts-dropdown',
  templateUrl: './toasts-dropdown.component.html',
  styleUrls: ['./toasts-dropdown.component.scss'],
  imports: [
    ToastComponent,
    NgbDropdownModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
})
export class ToastsDropdownComponent {
  toastService = inject(ToastService)
  private destroyRef = inject(DestroyRef)
  private clock: Subscription

  @ViewChild(NgbDropdown) dropdown: NgbDropdown

  /** Drives the relative timestamps, ticks only while the dropdown is open */
  readonly now = signal(new Date())

  /** Notifications that were unread when the dropdown was opened */
  readonly newIds = signal(new Set<string>())

  readonly toasts = toSignal(
    this.toastService.getToasts().pipe(map((toasts) => [...toasts])),
    { initialValue: [] as Toast[] }
  )

  readonly unread = computed(() => this.toasts().filter((t) => !t.read))

  readonly hasUnreadError = computed(() =>
    this.unread().some((t) => t.level === ToastLevel.Error)
  )

  onOpenChange(open: boolean): void {
    this.toastService.suppressPopupToasts = open
    this.clock?.unsubscribe()
    this.newIds.set(new Set(open ? this.unread().map((t) => t.id) : []))
    if (open) {
      this.toastService.markAllRead()
      this.now.set(new Date())
      this.clock = interval(30000)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(() => this.now.set(new Date()))
    }
  }

  /** Using an action (Undo, Open document...) clears it and closes the menu */
  onActioned(toast: Toast): void {
    this.toastService.closeToast(toast)
    this.dropdown?.close()
  }
}
