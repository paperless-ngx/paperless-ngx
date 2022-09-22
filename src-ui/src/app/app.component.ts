import { SettingsService } from './services/settings.service'
import { SETTINGS_KEYS } from './data/paperless-uisettings'
import { Component, OnDestroy, OnInit, Renderer2 } from '@angular/core'
import { Router } from '@angular/router'
import { Subscription } from 'rxjs'
import { ConsumerStatusService } from './services/consumer-status.service'
import { ToastService } from './services/toast.service'
import { NgxFileDropEntry } from 'ngx-file-drop'
import { UploadDocumentsService } from './services/upload-documents.service'
import { TasksService } from './services/tasks.service'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit, OnDestroy {
  newDocumentSubscription: Subscription
  successSubscription: Subscription
  failedSubscription: Subscription

  private fileLeaveTimeoutID: any
  fileIsOver: boolean = false
  hidden: boolean = true

  constructor(
    private settings: SettingsService,
    private consumerStatusService: ConsumerStatusService,
    private toastService: ToastService,
    private router: Router,
    private uploadDocumentsService: UploadDocumentsService,
    private tasksService: TasksService,
    public tourService: TourService,
    private renderer: Renderer2
  ) {
    let anyWindow = window as any
    anyWindow.pdfWorkerSrc = 'assets/js/pdf.worker.min.js'
    this.settings.updateAppearanceSettings()
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
    if (
      this.router.url == '/dashboard' &&
      this.settings.get(
        SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUPPRESS_ON_DASHBOARD
      )
    ) {
      return false
    }
    return this.settings.get(key)
  }

  ngOnInit(): void {
    this.consumerStatusService.connect()

    this.successSubscription = this.consumerStatusService
      .onDocumentConsumptionFinished()
      .subscribe((status) => {
        this.tasksService.reload()
        if (
          this.showNotification(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_SUCCESS)
        ) {
          this.toastService.show({
            title: $localize`Document added`,
            delay: 10000,
            content: $localize`Document ${status.filename} was added to paperless.`,
            actionName: $localize`Open document`,
            action: () => {
              this.router.navigate(['documents', status.documentId])
            },
          })
        }
      })

    this.failedSubscription = this.consumerStatusService
      .onDocumentConsumptionFailed()
      .subscribe((status) => {
        this.tasksService.reload()
        if (
          this.showNotification(SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_FAILED)
        ) {
          this.toastService.showError(
            $localize`Could not add ${status.filename}\: ${status.message}`
          )
        }
      })

    this.newDocumentSubscription = this.consumerStatusService
      .onDocumentDetected()
      .subscribe((status) => {
        this.tasksService.reload()
        if (
          this.showNotification(
            SETTINGS_KEYS.NOTIFICATIONS_CONSUMER_NEW_DOCUMENT
          )
        ) {
          this.toastService.show({
            title: $localize`New document detected`,
            delay: 5000,
            content: $localize`Document ${status.filename} is being processed by paperless.`,
          })
        }
      })

    this.tourService.initialize([
      {
        anchorId: 'tour.intro',
        title: `Hello ${this.settings.displayName}, welcome to Paperless-ngx!`,
        content:
          "Here's a tutorial to guide you around some of Paperless-ngx's most useful features.",
        route: '/dashboard',
      },
      {
        anchorId: 'tour.dashboard',
        title: 'The Dashboard',
        content: "Here's some dashboard info",
        route: '/dashboard',
      },
      {
        anchorId: 'tour.documents',
        title: 'Documents List',
        content: "Here's some dashboard info",
        route: '/documents',
        delayAfterNavigation: 500,
      },
    ])

    this.tourService.start$.subscribe(() => {
      this.renderer.addClass(document.body, 'tour-active')
    })

    this.tourService.end$.subscribe(() => {
      // animation time
      setTimeout(() => {
        this.renderer.removeClass(document.body, 'tour-active')
      }, 500)
    })
  }

  public get dragDropEnabled(): boolean {
    return !this.router.url.includes('dashboard')
  }

  public fileOver() {
    // allows transition
    setTimeout(() => {
      this.fileIsOver = true
    }, 1)
    this.hidden = false
    // stop fileLeave timeout
    clearTimeout(this.fileLeaveTimeoutID)
  }

  public fileLeave(immediate: boolean = false) {
    const ms = immediate ? 0 : 500

    this.fileLeaveTimeoutID = setTimeout(() => {
      this.fileIsOver = false
      // await transition completed
      setTimeout(() => {
        this.hidden = true
      }, 150)
    }, ms)
  }

  public dropped(files: NgxFileDropEntry[]) {
    this.fileLeave(true)
    this.uploadDocumentsService.uploadFiles(files)
    this.toastService.showInfo($localize`Initiating upload...`, 3000)
  }
}
