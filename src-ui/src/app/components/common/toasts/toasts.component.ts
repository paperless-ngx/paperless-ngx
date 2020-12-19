import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { Toast, ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-toasts',
  templateUrl: './toasts.component.html',
  styleUrls: ['./toasts.component.scss']
})
export class ToastsComponent implements OnInit, OnDestroy {

  constructor(private toastService: ToastService) { }

  subscription: Subscription

  toasts: Toast[] = []

  ngOnDestroy(): void {
    this.subscription.unsubscribe()
  }

  ngOnInit(): void {
    this.subscription = this.toastService.getToasts().subscribe(toasts => this.toasts = toasts)
  }

}
