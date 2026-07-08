import { Component, inject } from '@angular/core'
import { toSignal } from '@angular/core/rxjs-interop'
import {
  NgbAccordionModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { map, merge, Subject } from 'rxjs'
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
export class ToastsComponent {
  toastService = inject(ToastService)

  private readonly closedToast = new Subject<void>()

  readonly toasts = toSignal(
    merge(
      this.toastService.showToast.pipe(map((toast) => (toast ? [toast] : []))),
      this.closedToast.pipe(map(() => [] as Toast[]))
    ),
    { initialValue: [] as Toast[] }
  )

  closeToast() {
    this.toastService.closeToast(this.toasts()[0])
    this.closedToast.next()
  }
}
