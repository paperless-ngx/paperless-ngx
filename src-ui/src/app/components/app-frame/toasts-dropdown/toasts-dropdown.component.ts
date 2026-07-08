import { Component, inject } from '@angular/core'
import { toSignal } from '@angular/core/rxjs-interop'
import {
  NgbDropdownModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { map } from 'rxjs'
import { Toast, ToastService } from 'src/app/services/toast.service'
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

  readonly toasts = toSignal(
    this.toastService.getToasts().pipe(map((toasts) => [...toasts])),
    { initialValue: [] as Toast[] }
  )

  onOpenChange(open: boolean): void {
    this.toastService.suppressPopupToasts = open
  }
}
