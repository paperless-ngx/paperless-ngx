import { Clipboard } from '@angular/cdk/clipboard'
import { DecimalPipe, NgClass, NgTemplateOutlet } from '@angular/common'
import {
  Component,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChildren,
} from '@angular/core'
import { Router, RouterModule } from '@angular/router'
import {
  NgbAlert,
  NgbAlertModule,
  NgbCollapseModule,
  NgbProgressbarModule,
  NgbToastModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subscription, interval, take } from 'rxjs'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  ConsumerStatusService,
  FileStatus,
  FileStatusPhase,
} from 'src/app/services/consumer-status.service'
import { SettingsService } from 'src/app/services/settings.service'
import { Toast, ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

const MAX_ALERTS = 5

@Component({
  selector: 'pngx-notifications',
  templateUrl: './notifications.component.html',
  styleUrls: ['./notifications.component.scss'],
  imports: [
    IfPermissionsDirective,
    DecimalPipe,
    RouterModule,
    NgClass,
    NgTemplateOutlet,
    NgbAlertModule,
    NgbCollapseModule,
    NgbToastModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
})
export class NotificationsComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  constructor(
    public toastService: ToastService,
    private clipboard: Clipboard,
    private consumerStatusService: ConsumerStatusService,
    private settingsService: SettingsService,
    private router: Router
  ) {
    super()
    this.router.events.subscribe(() => {
      if (!this.onDashboard) {
        this.consumerStatusService.dismissCompleted()
      }
    })
  }

  private subscription: Subscription

  public toasts: Toast[] = []

  public copied: boolean = false

  public seconds: number = 0

  public alertsExpanded = false

  @ViewChildren(NgbAlert) alerts: QueryList<NgbAlert>

  ngOnDestroy(): void {
    this.subscription?.unsubscribe()
  }

  ngOnInit(): void {
    this.subscription = this.toastService.getToasts().subscribe((toasts) => {
      this.toasts = toasts
      this.toasts.forEach((t) => {
        if (typeof t.error === 'string') {
          try {
            t.error = JSON.parse(t.error)
          } catch (e) {}
        }
      })
    })
  }

  onShow(toast: Toast) {
    const refreshInterval = 150
    const delay = toast.delay - 500 // for fade animation

    interval(refreshInterval)
      .pipe(take(delay / refreshInterval))
      .subscribe((count) => {
        toast.delayRemaining = Math.max(
          0,
          delay - refreshInterval * (count + 1)
        )
      })
  }

  public isDetailedError(error: any): boolean {
    return (
      typeof error === 'object' &&
      'status' in error &&
      'statusText' in error &&
      'url' in error &&
      'message' in error &&
      'error' in error
    )
  }

  public copyError(error: any) {
    this.clipboard.copy(JSON.stringify(error))
    this.copied = true
    setTimeout(() => {
      this.copied = false
    }, 3000)
  }

  getErrorText(error: any) {
    let text: string = error.error?.detail ?? error.error ?? ''
    if (typeof text === 'object') text = JSON.stringify(text)
    return `${text.slice(0, 200)}${text.length > 200 ? '...' : ''}`
  }

  get onDashboard(): boolean {
    return this.router.url == '/dashboard'
  }

  getStatus() {
    return this.consumerStatusService.getConsumerStatus().slice(0, MAX_ALERTS)
  }

  getStatusSummary() {
    let strings = []
    let countUploadingAndProcessing =
      this.consumerStatusService.getConsumerStatusNotCompleted().length
    let countFailed = this.getStatusFailed().length
    let countSuccess = this.getStatusSuccess().length
    if (countUploadingAndProcessing > 0) {
      strings.push($localize`Processing: ${countUploadingAndProcessing}`)
    }
    if (countFailed > 0) {
      strings.push($localize`Failed: ${countFailed}`)
    }
    if (countSuccess > 0) {
      strings.push($localize`Added: ${countSuccess}`)
    }
    return strings.join(
      $localize`:this string is used to separate processing, failed and added on the file upload widget:, `
    )
  }

  getStatusHidden() {
    if (this.consumerStatusService.getConsumerStatus().length < MAX_ALERTS)
      return []
    else return this.consumerStatusService.getConsumerStatus().slice(MAX_ALERTS)
  }

  getStatusUploading() {
    return this.consumerStatusService.getConsumerStatus(
      FileStatusPhase.UPLOADING
    )
  }

  getStatusFailed() {
    return this.consumerStatusService.getConsumerStatus(FileStatusPhase.FAILED)
  }

  getStatusSuccess() {
    return this.consumerStatusService.getConsumerStatus(FileStatusPhase.SUCCESS)
  }

  getStatusCompleted() {
    return this.consumerStatusService.getConsumerStatusCompleted()
  }

  getTotalUploadProgress() {
    let current = 0
    let max = 0

    this.getStatusUploading().forEach((status) => {
      current += status.currentPhaseProgress
      max += status.currentPhaseMaxProgress
    })

    return current / Math.max(max, 1)
  }

  isFinished(status: FileStatus) {
    return (
      status.phase == FileStatusPhase.FAILED ||
      status.phase == FileStatusPhase.SUCCESS
    )
  }

  getStatusColor(status: FileStatus) {
    switch (status.phase) {
      case FileStatusPhase.UPLOADING:
      case FileStatusPhase.STARTED:
      case FileStatusPhase.WORKING:
        return 'primary'
      case FileStatusPhase.FAILED:
        return 'danger'
      case FileStatusPhase.SUCCESS:
        return 'success'
    }
  }

  dismiss(status: FileStatus) {
    this.consumerStatusService.dismiss(status)
  }

  dismissCompleted() {
    this.getStatusCompleted().forEach((status) =>
      this.consumerStatusService.dismiss(status)
    )
  }

  get slimSidebarEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.SLIM_SIDEBAR)
  }
}
