import { Component, ElementRef, QueryList, ViewChild, ViewChildren } from '@angular/core'
import { Router } from '@angular/router'
import { NgbAlert } from '@ng-bootstrap/ng-bootstrap'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { ConsumerStatusService, FileStatus, FileStatusPhase } from 'src/app/services/consumer-status.service'
import { SettingsService } from 'src/app/services/settings.service'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'

const MAX_ALERTS = 5

@Component({
  selector: 'pngx-upload-file-btn',
  templateUrl: './upload-file-btn.component.html',
  styleUrls: ['./upload-file-btn.component.scss'],
})
export class UploadFileButtonComponent extends ComponentWithPermissions {
  alertsExpanded = false
  @ViewChild('fileUpload', { static: false }) fileUpload!: ElementRef



  @ViewChildren(NgbAlert) alerts: QueryList<NgbAlert>


  constructor(
    private router: Router,
    private consumerStatusService: ConsumerStatusService,
    private uploadDocumentsService: UploadDocumentsService,
    public settingsService: SettingsService,
  ) {
    super()
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
      $localize`:this string is used to separate processing, failed and added on the file upload widget:, `,
    )
  }

  getStatusHidden() {
    if (this.consumerStatusService.getConsumerStatus().length < MAX_ALERTS)
      return []
    else return this.consumerStatusService.getConsumerStatus().slice(MAX_ALERTS)
  }

  getStatusUploading() {
    return this.consumerStatusService.getConsumerStatus(
      FileStatusPhase.UPLOADING,
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
      this.consumerStatusService.dismiss(status),
    )
  }

  public onFileSelected(event: Event) {
    let getUrl = this.router.url.split('/')
    let payload = { folder: '', dossiers: '' }
    const folderMatch = this.router.url.match(/folders\/(\d+)/)
    const dossierMatch = this.router.url.match(/dossiers\/(\d+)/)
    if (folderMatch) {
      payload.folder = folderMatch[1]
    }
    if (dossierMatch) {
      payload.dossiers = dossierMatch[1]
    }
    this.uploadDocumentsService.uploadFiles(
      (event.target as HTMLInputElement).files,
      payload,
    )
  }

  // resetFileInput() {
  //   this.fileUpload.nativeElement.value = ''
  // }

  get slimSidebarEnabled(): boolean {
    return this.settingsService.get(SETTINGS_KEYS.SLIM_SIDEBAR)
  }
}
