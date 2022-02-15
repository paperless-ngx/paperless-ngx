import { HttpEventType } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop';
import { ConsumerStatusService, FileStatus, FileStatusPhase } from 'src/app/services/consumer-status.service';
import { DocumentService } from 'src/app/services/rest/document.service';

const MAX_ALERTS = 5

@Component({
  selector: 'app-upload-file-widget',
  templateUrl: './upload-file-widget.component.html',
  styleUrls: ['./upload-file-widget.component.scss']
})
export class UploadFileWidgetComponent implements OnInit {
  alertsExpanded = false

  constructor(
    private documentService: DocumentService,
    private consumerStatusService: ConsumerStatusService
  ) { }

  getStatus() {
    return this.consumerStatusService.getConsumerStatus().slice(0, MAX_ALERTS)
  }

  getStatusSummary() {
    let strings = []
    let countUploadingAndProcessing =  this.consumerStatusService.getConsumerStatusNotCompleted().length
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
    return strings.join($localize`:this string is used to separate processing, failed and added on the file upload widget:, `)
  }

  getStatusHidden() {
    if (this.consumerStatusService.getConsumerStatus().length < MAX_ALERTS) return []
    else return this.consumerStatusService.getConsumerStatus().slice(MAX_ALERTS)
  }

  getStatusUploading() {
    return this.consumerStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
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

    this.getStatusUploading().forEach(status => {
      current += status.currentPhaseProgress
      max += status.currentPhaseMaxProgress
    })

    return current / Math.max(max, 1)
  }

  isFinished(status: FileStatus) {
    return status.phase == FileStatusPhase.FAILED || status.phase == FileStatusPhase.SUCCESS
  }

  getStatusColor(status: FileStatus) {
    switch (status.phase) {
      case FileStatusPhase.PROCESSING:
      case FileStatusPhase.UPLOADING:
          return "primary"
      case FileStatusPhase.FAILED:
        return "danger"
      case FileStatusPhase.SUCCESS:
        return "success"
    }
  }

  dismiss(status: FileStatus) {
    this.consumerStatusService.dismiss(status)
  }

  dismissCompleted() {
    this.consumerStatusService.dismissCompleted()
  }

  ngOnInit(): void {
  }

  public fileOver(event){
  }

  public fileLeave(event){
  }

  public dropped(files: NgxFileDropEntry[]) {
    for (const droppedFile of files) {
      if (droppedFile.fileEntry.isFile) {

      const fileEntry = droppedFile.fileEntry as FileSystemFileEntry;
        fileEntry.file((file: File) => {
          let formData = new FormData()
          formData.append('document', file, file.name)
          let status = this.consumerStatusService.newFileUpload(file.name)

          status.message = $localize`Connecting...`

          this.documentService.uploadDocument(formData).subscribe(event => {
            if (event.type == HttpEventType.UploadProgress) {
              status.updateProgress(FileStatusPhase.UPLOADING, event.loaded, event.total)
              status.message = $localize`Uploading...`
            } else if (event.type == HttpEventType.Response) {
              status.taskId = event.body["task_id"]
              status.message = $localize`Upload complete, waiting...`
            }

          }, error => {
            switch (error.status) {
              case 400: {
                this.consumerStatusService.fail(status, error.error.document)
                break;
              }
              default: {
                this.consumerStatusService.fail(status, $localize`HTTP error: ${error.status} ${error.statusText}`)
                break;
              }
            }

          })
        });
      }
    }
  }
}
