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
        anchorId: 'tour.dashboard',
        content: $localize`The dashboard can be used to show saved views, such as an 'Inbox'. Those settings are found under Settings > Saved Views once you have created some.`,
        route: '/dashboard',
      },
      {
        anchorId: 'tour.upload-widget',
        content: $localize`Drag-and-drop documents here to start uploading or place them in the consume folder. You can also drag-and-drop documents anywhere on all other pages of the web app. Once you do, Paperless-ngx will start training it's machine learning algorithms.`,
        route: '/dashboard',
      },
      {
        anchorId: 'tour.documents',
        content: $localize`The documents list shows all of your documents and allows for filtering as well as bulk-editing. There are three different view styles: list, small cards and large cards. A list of documents currently opened for editing is shown in the sidebar.`,
        route: '/documents',
        delayAfterNavigation: 500,
        placement: 'bottom',
      },
      {
        anchorId: 'tour.documents-filter-editor',
        content: $localize`The filtering tools allow you to quickly find documents using various searches, dates, tags, etc.`,
        route: '/documents',
        placement: 'bottom',
      },
      {
        anchorId: 'tour.documents-views',
        content: $localize`Any combination of filters can be saved as a 'view' which can then be displayed on the dashboard and / or sidebar.`,
        route: '/documents',
      },
      {
        anchorId: 'tour.tags',
        content: $localize`Tags, correspondents, document types and storage paths can all be managed using these pages. They can also be created from the document edit view.`,
        route: '/tags',
      },
      {
        anchorId: 'tour.file-tasks',
        content: $localize`File Tasks shows you documents that have been consumed, are waiting to be, or may have failed during the process.`,
        route: '/tasks',
      },
      {
        anchorId: 'tour.settings',
        content: $localize`Check out the settings for various tweaks to the web app or to toggle settings for saved views.`,
        route: '/settings',
      },
      {
        anchorId: 'tour.admin',
        content: $localize`The Admin area contains more advanced controls as well as the settings for automatic e-mail fetching.`,
      },
      {
        anchorId: 'tour.outro',
        title: $localize`Thank you! 🙏`,
        content:
          $localize`There are <em>tons</em> more features and info we didn't cover here, but this should get you started. Check out the documentation or visit the project on GitHub to learn more or to report issues.` +
          '<br/><br/>' +
          $localize`Lastly, on behalf of every contributor to this community-supported project, thank you for using Paperless-ngx!`,
        route: '/dashboard',
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
