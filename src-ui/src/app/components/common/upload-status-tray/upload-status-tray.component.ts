import { NgClass, NgTemplateOutlet } from '@angular/common'
import { Component, effect, inject, signal } from '@angular/core'
import { takeUntilDestroyed } from '@angular/core/rxjs-interop'
import { RouterModule } from '@angular/router'
import {
  NgbAlertModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { SettingsService } from 'src/app/services/settings.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'
import {
  FileStatus,
  FileStatusPhase,
  WebsocketStatusService,
} from 'src/app/services/websocket-status.service'

/** Floating list of document consumption statuses, shown on every page */
@Component({
  selector: 'pngx-upload-status-tray',
  templateUrl: './upload-status-tray.component.html',
  styleUrls: ['./upload-status-tray.component.scss'],
  imports: [
    IfPermissionsDirective,
    NgClass,
    NgTemplateOutlet,
    RouterModule,
    NgbAlertModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
  ],
})
export class UploadStatusTrayComponent extends ComponentWithPermissions {
  private websocketStatusService = inject(WebsocketStatusService)
  private settingsService = inject(SettingsService)
  private permissionsService = inject(PermissionsService)
  private uploadDocumentsService = inject(UploadDocumentsService)

  readonly collapsed = signal(false)

  constructor() {
    super()
    // start expanded again for the next uploads once everything is dismissed
    effect(() => {
      if (this.getStatus().length === 0) this.collapsed.set(false)
    })
    this.uploadDocumentsService
      .onUploadsStarted()
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.expand())
  }

  get canAddDocuments(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.Add,
      PermissionType.Document
    )
  }

  getStatus() {
    return this.websocketStatusService.getConsumerStatus()
  }

  getStatusSummary() {
    let strings = []
    let countUploadingAndProcessing =
      this.websocketStatusService.getConsumerStatusNotCompleted().length
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

  getStatusUploading() {
    return this.websocketStatusService.getConsumerStatus(
      FileStatusPhase.UPLOADING
    )
  }

  getStatusFailed() {
    return this.websocketStatusService.getConsumerStatus(FileStatusPhase.FAILED)
  }

  getStatusSuccess() {
    return this.websocketStatusService.getConsumerStatus(
      FileStatusPhase.SUCCESS
    )
  }

  getStatusCompleted() {
    return this.websocketStatusService.getConsumerStatusCompleted()
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

  toggleCollapsed() {
    this.collapsed.update((collapsed) => !collapsed)
  }

  expand() {
    this.collapsed.set(false)
  }

  dismiss(status: FileStatus) {
    this.websocketStatusService.dismiss(status)
  }

  dismissCompleted() {
    this.getStatusCompleted().forEach((status) =>
      this.websocketStatusService.dismiss(status)
    )
  }

  get slimSidebarEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.SLIM_SIDEBAR)
  }
}
