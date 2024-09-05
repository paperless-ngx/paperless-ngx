import { SettingsService } from './services/settings.service'
import { SETTINGS_KEYS } from './data/ui-settings'
import { Component, OnDestroy, OnInit, Renderer2 } from '@angular/core'
import { Router } from '@angular/router'
import { Subscription, first } from 'rxjs'
import { ConsumerStatusService } from './services/consumer-status.service'
import { ToastService } from './services/toast.service'
import { TasksService } from './services/tasks.service'
import { TourService } from 'ngx-ui-tour-ng-bootstrap'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from './services/permissions.service'
import { HotKeyService } from './services/hot-key.service'

@Component({
  selector: 'pngx-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit, OnDestroy {
  newDocumentSubscription: Subscription
  successSubscription: Subscription
  failedSubscription: Subscription

  constructor(
    private settings: SettingsService,
    private consumerStatusService: ConsumerStatusService,
    private toastService: ToastService,
    private router: Router,
    private tasksService: TasksService,
    public tourService: TourService,
    private renderer: Renderer2,
    private permissionsService: PermissionsService,
    private hotKeyService: HotKeyService
  ) {
    let anyWindow = window as any
    anyWindow.pdfWorkerSrc = 'assets/js/pdf.worker.min.mjs'
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
          if (
            this.permissionsService.currentUserCan(
              PermissionAction.View,
              PermissionType.Document
            )
          ) {
            this.toastService.show({
              content: $localize`Document ${status.filename} was added to Paperless-ngx.`,
              delay: 10000,
              actionName: $localize`Open document`,
              action: () => {
                this.router.navigate(['documents', status.documentId])
              },
            })
          } else {
            this.toastService.show({
              content: $localize`Document ${status.filename} was added to Paperless-ngx.`,
              delay: 10000,
            })
          }
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
            content: $localize`Document ${status.filename} is being processed by Paperless-ngx.`,
            delay: 5000,
          })
        }
      })

    this.hotKeyService
      .addShortcut({ keys: 'h', description: $localize`Dashboard` })
      .subscribe(() => {
        this.router.navigate(['/dashboard'])
      })
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Document
      )
    ) {
      this.hotKeyService
        .addShortcut({ keys: 'd', description: $localize`Documents` })
        .subscribe(() => {
          this.router.navigate(['/documents'])
        })
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.Change,
        PermissionType.UISettings
      )
    ) {
      this.hotKeyService
        .addShortcut({ keys: 's', description: $localize`Settings` })
        .subscribe(() => {
          this.router.navigate(['/settings'])
        })
    }

    const prevBtnTitle = $localize`Prev`
    const nextBtnTitle = $localize`Next`
    const endBtnTitle = $localize`End`

    this.tourService.initialize(
      [
        {
          anchorId: 'tour.dashboard',
          content: $localize`The dashboard can be used to show saved views, such as an 'Inbox'. Those settings are found under Settings > Saved Views once you have created some.`,
          route: '/dashboard',
          delayAfterNavigation: 500,
          isOptional: false,
        },
        {
          anchorId: 'tour.upload-widget',
          content: $localize`Drag-and-drop documents here to start uploading or place them in the consume folder. You can also drag-and-drop documents anywhere on all other pages of the web app. Once you do, Paperless-ngx will start training its machine learning algorithms.`,
          route: '/dashboard',
        },
        {
          anchorId: 'tour.documents',
          content: $localize`The documents list shows all of your documents and allows for filtering as well as bulk-editing. There are three different view styles: list, small cards and large cards. A list of documents currently opened for editing is shown in the sidebar.`,
          route: '/documents?sort=created&reverse=1&page=1',
          delayAfterNavigation: 500,
          placement: 'bottom',
        },
        {
          anchorId: 'tour.documents-filter-editor',
          content: $localize`The filtering tools allow you to quickly find documents using various searches, dates, tags, etc.`,
          route: '/documents?sort=created&reverse=1&page=1',
          placement: 'bottom',
        },
        {
          anchorId: 'tour.documents-views',
          content: $localize`Any combination of filters can be saved as a 'view' which can then be displayed on the dashboard and / or sidebar.`,
          route: '/documents?sort=created&reverse=1&page=1',
        },
        {
          anchorId: 'tour.tags',
          content: $localize`Tags, correspondents, document types and storage paths can all be managed using these pages. They can also be created from the document edit view.`,
          route: '/tags',
          backdropConfig: {
            offset: 0,
          },
        },
        {
          anchorId: 'tour.mail',
          content: $localize`Manage e-mail accounts and rules for automatically importing documents.`,
          route: '/mail',
          backdropConfig: {
            offset: 0,
          },
        },
        {
          anchorId: 'tour.workflows',
          content: $localize`Workflows give you more control over the document pipeline.`,
          route: '/workflows',
          backdropConfig: {
            offset: 0,
          },
        },
        {
          anchorId: 'tour.file-tasks',
          content: $localize`File Tasks shows you documents that have been consumed, are waiting to be, or may have failed during the process.`,
          route: '/tasks',
          backdropConfig: {
            offset: 0,
          },
        },
        {
          anchorId: 'tour.settings',
          content: $localize`Check out the settings for various tweaks to the web app and toggle settings for saved views.`,
          route: '/settings',
          backdropConfig: {
            offset: 0,
          },
        },
        {
          anchorId: 'tour.outro',
          title: $localize`Thank you! 🙏`,
          content:
            $localize`There are <em>tons</em> more features and info we didn't cover here, but this should get you started. Check out the documentation or visit the project on GitHub to learn more or to report issues.` +
            '<br/><br/>' +
            $localize`Lastly, on behalf of every contributor to this community-supported project, thank you for using Paperless-ngx!`,
          route: '/dashboard',
          isOptional: false,
          backdropConfig: {
            offset: 0,
          },
        },
      ],
      {
        enableBackdrop: true,
        backdropConfig: {
          offset: 10,
        },
        prevBtnTitle,
        nextBtnTitle,
        endBtnTitle,
        isOptional: true,
        useLegacyTitle: true,
      }
    )

    this.tourService.start$.subscribe(() => {
      this.renderer.addClass(document.body, 'tour-active')

      this.tourService.end$.pipe(first()).subscribe(() => {
        this.settings.completeTour()
        // animation time
        setTimeout(() => {
          this.renderer.removeClass(document.body, 'tour-active')
        }, 500)
      })
    })
  }
}
