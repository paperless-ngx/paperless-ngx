import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core'
import {
  NgbAccordionModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription } from 'rxjs'
import { Toast, ToastService } from 'src/app/services/toast.service'
import { ToastComponent } from '../toast/toast.component'

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
export class ToastsComponent implements OnInit, OnDestroy {
  toastService = inject(ToastService)

  private subscription: Subscription

  private toastsSignal = signal<Toast[]>([])

  public get toasts(): Toast[] {
    return this.toastsSignal()
  }

  public set toasts(toasts: Toast[]) {
    this.toastsSignal.set(toasts)
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe()
  }

  ngOnInit(): void {
    this.subscription = this.toastService.showToast.subscribe((toast) => {
      this.toasts = toast ? [toast] : []
    })
  }

  closeToast() {
    this.toastService.closeToast(this.toasts[0])
    this.toasts = []
  }
}
