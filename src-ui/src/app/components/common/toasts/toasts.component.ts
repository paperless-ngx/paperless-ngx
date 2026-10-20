import { Component, inject, signal } from '@angular/core'
import { takeUntilDestroyed } from '@angular/core/rxjs-interop'
import {
  NgbAccordionModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Toast, ToastService } from 'src/app/services/toast.service'
import { ToastComponent } from '../toast/toast.component'

/**
 * Maximum number of popup toasts shown at once
 */
export const MAX_VISIBLE_TOASTS = 3

@Component({
  selector: 'pngx-toasts',
  templateUrl: './toasts.component.html',
  styleUrls: ['./toasts.component.scss'],
  imports: [
    ToastComponent,
    NgbAccordionModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
})
export class ToastsComponent {
  toastService = inject(ToastService)

  readonly toasts = signal<Toast[]>([])

  constructor() {
    this.toastService.showToast
      .pipe(takeUntilDestroyed())
      .subscribe((toast) => {
        if (!toast) {
          this.toasts.set([])
          return
        }
        this.toasts.update((toasts) =>
          [toast, ...toasts.filter((t) => t.id !== toast.id)].slice(
            0,
            MAX_VISIBLE_TOASTS
          )
        )
      })
  }

  closeToast(toast: Toast) {
    this.toastService.closeToast(toast)
    this.removePopup(toast)
  }

  removePopup(toast: Toast) {
    this.toasts.update((toasts) => toasts.filter((t) => t.id !== toast.id))
  }
}
