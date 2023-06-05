import { Injectable } from '@angular/core'
import { HttpEventType } from '@angular/common/http'
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop'
import {
  ConsumerStatusService,
  FileStatusPhase,
} from './consumer-status.service'
import { DocumentService } from './rest/document.service'
import { Subscription } from 'rxjs'
import { SettingsService } from './settings.service'

@Injectable({
  providedIn: 'root',
})
export class UploadDocumentsService {
  private uploadSubscriptions: Array<Subscription> = []

  constructor(
    private documentService: DocumentService,
    private consumerStatusService: ConsumerStatusService,
    private settings: SettingsService
  ) {}

  uploadFiles(files: NgxFileDropEntry[], merge: boolean = false, filename: string = null) {
    let sendFormData = (formData: FormData, filename: string) => {
      let status = this.consumerStatusService.newFileUpload(filename)

      status.message = $localize`Connecting...`

      this.uploadSubscriptions[filename] = this.documentService
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
              status.taskId = event.body['task_id']
              status.message = $localize`Upload complete, waiting...`
              this.uploadSubscriptions[filename]?.complete()
            }
          },
          error: (error) => {
            switch (error.status) {
              case 400: {
                this.consumerStatusService.fail(
                  status,
                  error.error.document
                )
                break
              }
              default: {
                this.consumerStatusService.fail(
                  status,
                  $localize`HTTP error: ${error.status} ${error.statusText}`
                )
                break
              }
            }
            this.uploadSubscriptions[filename]?.complete()
          },
        })
    }

    let formData = new FormData()

    for (const droppedFile of files) {
      if (droppedFile.fileEntry.isFile) {
        const fileEntry = droppedFile.fileEntry as FileSystemFileEntry
        fileEntry.file((file: File) => {
          if (merge) {
            formData.append('document', file, file.name)
          } else {
            formData.set('document', file, file.name)
            sendFormData(formData, file.name)
          }
        })
      }
    }

    if (merge) {
      if (!filename) {
        filename = "merged_virtual_file.pdf"
      }

      formData.append('filename', filename)
      sendFormData(formData, filename)
    }
  }
}
