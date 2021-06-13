import { SettingsService, SETTINGS_KEYS } from './services/settings.service';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { ConsumerStatusService } from './services/consumer-status.service';
import { ToastService } from './services/toast.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit, OnDestroy {

  newDocumentSubscription: Subscription;
  successSubscription: Subscription;
  failedSubscription: Subscription;

  constructor (private settings: SettingsService, private consumerStatusService: ConsumerStatusService, private toastService: ToastService, private router: Router) {
    let anyWindow = (window as any)
    anyWindow.pdfWorkerSrc = 'assets/js/pdf.worker.min.js';
    this.settings.updateDarkModeSettings()
  }

  ngOnDestroy(): void {
    this.consumerStatusService.disconnect()
    if (this.successSubscription) {
      this.successSubscription.unsubscribe()
    }
    if (this.failedSubscription) {
      this.failedSubscription.unsubscribe()
    }
    if (this.newDocumentSubscription) {
      this.newDocumentSubscription.unsubscribe()
    }
  }

  private showNotification(key) {
    if (this.router.url == '/dashboard' && this.settings.get(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD)) {
      return false
    }
    return this.settings.get(key)
  }

  ngOnInit(): void {
    this.consumerStatusService.connect()


    this.successSubscription = this.consumerStatusService.onDocumentConsumptionFinished().subscribe(status => {
      if (this.showNotification(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUCCESS)) {
        this.toastService.show({title: $localize`Document added`, delay: 10000, content: $localize`Document ${status.filename} was added to paperless.`, actionName: $localize`Open document`, action: () => {
          this.router.navigate(['documents', status.documentId])
        }})
      }
    })

    this.failedSubscription = this.consumerStatusService.onDocumentConsumptionFailed().subscribe(status => {
      if (this.showNotification(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_FAILED)) {
        this.toastService.showError($localize`Could not add ${status.filename}\: ${status.message}`)
      }
    })

    this.newDocumentSubscription = this.consumerStatusService.onDocumentDetected().subscribe(status => {
      if (this.showNotification(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT)) {
        this.toastService.show({title: $localize`New document detected`, delay: 5000, content: $localize`Document ${status.filename} is being processed by paperless.`})
      }
    })
  }

}
