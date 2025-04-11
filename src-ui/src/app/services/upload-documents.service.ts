import { Injectable } from '@angular/core'
import { HttpEventType } from '@angular/common/http'
import { FileSystemFileEntry, NgxFileDropEntry } from 'ngx-file-drop'
import {
  ConsumerStatusService,
  FileStatusPhase,
} from './consumer-status.service'
import { DocumentService } from './rest/document.service'
import { Subscription } from 'rxjs'

@Injectable({
  providedIn: 'root',
})
export class UploadDocumentsService {
  private uploadSubscriptions: Array<Subscription> = []

  constructor(
    private documentService: DocumentService,
    private consumerStatusService: ConsumerStatusService
  ) {}

  onNgxFileDrop(files: NgxFileDropEntry[], payload) {
    for (const droppedFile of files) {
      if (droppedFile.fileEntry.isFile) {
        const fileEntry = droppedFile.fileEntry as FileSystemFileEntry
        fileEntry.file((file: File) => this.uploadFile(file, payload))
      }
    }
  }

  uploadFiles(files: FileList, payload) {
    for (let index = 0; index < files.length; index++) {
      this.uploadFile(files.item(index),payload)
    }
  }

  private uploadFile(file: File, payload) {
    // console.log("payload",payload)
    let formData = new FormData()
    formData.append('document', file, file.name)
    if (payload?.folder!='' && payload?.folder!='root' && payload?.folder!=undefined){
      formData.append('folder',payload.folder)
    }
    if (payload?.dossiers!='' && payload?.dossiers!=undefined){
      formData.append('dossier',payload.dossiers)


    }

    let status = this.consumerStatusService.newFileUpload(file.name)

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
            status.taskId = event.body['task_id']
            status.message = $localize`Upload complete, waiting...`
            this.uploadSubscriptions[file.name]?.complete()
          }
        },
        error: (error) => {
          switch (error.status) {
            case 400: {
              this.consumerStatusService.fail(status, error.error.document)
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
          this.uploadSubscriptions[file.name]?.complete()
        },
      })
    if (status.exist){
      status = null
    }
  }
}
