import { Component, OnDestroy, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { ConsumerStatusService } from './services/consumer-status.service';
import { Toast, ToastService } from './services/toast.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit, OnDestroy {

  successSubscription: Subscription;
  failedSubscription: Subscription;
  
  constructor ( private consumerStatusService: ConsumerStatusService, private toastService: ToastService, private router: Router ) {
  }

  ngOnDestroy(): void {
    this.consumerStatusService.disconnect()
    this.successSubscription.unsubscribe()
    this.failedSubscription.unsubscribe()
  }

  ngOnInit(): void {
    this.consumerStatusService.connect()

    this.successSubscription = this.consumerStatusService.onDocumentConsumptionFinished().subscribe(status => {
      this.toastService.showToast({title: "Document added", content: `Document ${status.filename} was added to paperless.`, actionName: "Open document", action: () => {
        this.router.navigate(['documents', status.document_id])
      }})
    })

    this.failedSubscription = this.consumerStatusService.onDocumentConsumptionFailed().subscribe(status => {
      this.toastService.showError(`Could not consume ${status.filename}: ${status.message}`)
    })

  }

  

}
