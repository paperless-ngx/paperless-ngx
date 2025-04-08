import { HttpEventType } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop'
import { Subscription } from 'rxjs'
import { DocumentService } from './rest/document.service'
import {
  FileStatusPhase,
  WebsocketStatusService,
} from './websocket-status.service'

@Injectable({
  providedIn: 'root',
})
export class UploadDocumentsService {
  private uploadSubscriptions: Array<Subscription> = []

  constructor(
    private documentService: DocumentService,
    private websocketStatusService: WebsocketStatusService
  ) {}

  onNgxFileDrop(files: NgxFileDropEntry[]) {
    for (const droppedFile of files) {
      if (droppedFile.fileEntry.isFile) {
        const fileEntry = droppedFile.fileEntry as FileSystemFileEntry
        fileEntry.file((file: File) => this.uploadFile(file))
      }
    }
  }

  uploadFiles(files: FileList) {
    for (let index = 0; index < files.length; index++) {
      this.uploadFile(files.item(index))
    }
  }

  private uploadFile(file: File) {
    let formData = new FormData()
    formData.append('document', file, file.name)
    formData.append('from_webui', 'true')
    let status = this.websocketStatusService.newFileUpload(file.name)

    status.message = $localize`Connecting...`

    this.uploadSubscriptions[file.name] = this.documentService
      .uploadDocument(formData)
      .subscribe({
        next: (event) => {
          if (event.type == HttpEventType.UploadProgress) {
            status.updateProgress(
              FileStatusPhase.UPLOADING,
              event.loaded,
              event.total
            )
            status.message = $localize`Uploading...`
          } else if (event.type == HttpEventType.Response) {
            status.taskId = event.body['task_id'] ?? event.body.toString()
            status.message = $localize`Upload complete, waiting...`
            this.uploadSubscriptions[file.name]?.complete()
          }
        },
        error: (error) => {
          switch (error.status) {
            case 400: {
              this.websocketStatusService.fail(status, error.error.document)
              break
            }
            default: {
              this.websocketStatusService.fail(
                status,
                $localize`HTTP error: ${error.status} ${error.statusText}`
              )
              break
            }
          }
          this.uploadSubscriptions[file.name]?.complete()
        },
      })
  }
}
