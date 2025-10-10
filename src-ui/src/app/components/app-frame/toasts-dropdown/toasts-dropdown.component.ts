import { Component, OnDestroy, OnInit, inject } from '@angular/core'
import {
  NgbDropdownModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription } from 'rxjs'
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
export class ToastsDropdownComponent implements OnInit, OnDestroy {
  toastService = inject(ToastService)

  private subscription: Subscription

  public toasts: Toast[] = []

  ngOnDestroy(): void {
    this.subscription?.unsubscribe()
  }

  ngOnInit(): void {
    this.subscription = this.toastService.getToasts().subscribe((toasts) => {
      this.toasts = [...toasts]
    })
  }

  onOpenChange(open: boolean): void {
    this.toastService.suppressPopupToasts = open
  }
}
