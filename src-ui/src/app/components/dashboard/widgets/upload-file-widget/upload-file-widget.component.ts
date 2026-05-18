import { NgClass, NgTemplateOutlet } from '@angular/common'
import { Component, QueryList, ViewChildren, inject } from '@angular/core'
import { RouterModule } from '@angular/router'
import {
  NgbAlert,
  NgbAlertModule,
  NgbProgressbarModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TourNgBootstrap } from 'ngx-ui-tour-ng-bootstrap'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SettingsService } from 'src/app/services/settings.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'
import {
  FileStatus,
  FileStatusPhase,
  WebsocketStatusService,
} from 'src/app/services/websocket-status.service'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'

@Component({
  selector: 'pngx-upload-file-widget',
  templateUrl: './upload-file-widget.component.html',
  styleUrls: ['./upload-file-widget.component.scss'],
  imports: [
    WidgetFrameComponent,
    IfPermissionsDirective,
    NgClass,
    NgTemplateOutlet,
    RouterModule,
    NgbAlertModule,
    NgbProgressbarModule,
    NgxBootstrapIconsModule,
    TourNgBootstrap,
  ],
})
export class UploadFileWidgetComponent extends ComponentWithPermissions {
  private websocketStatusService = inject(WebsocketStatusService)
  private uploadDocumentsService = inject(UploadDocumentsService)
  settingsService = inject(SettingsService)

  @ViewChildren(NgbAlert) alerts: QueryList<NgbAlert>

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

  dismiss(status: FileStatus) {
    this.websocketStatusService.dismiss(status)
  }

  dismissCompleted() {
    this.getStatusCompleted().forEach((status) =>
      this.websocketStatusService.dismiss(status)
    )
  }

  public onFileSelected(event: Event) {
    const files = (event.target as HTMLInputElement).files
    for (let i = 0; i < files?.length; i++) {
      const file = files.item(i)
      file && this.uploadDocumentsService.uploadFile(file)
    }
  }

  get slimSidebarEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.SLIM_SIDEBAR)
  }
}
