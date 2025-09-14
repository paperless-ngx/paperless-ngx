import { HttpEventType } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Subscription } from 'rxjs'
import { ConfigService } from './config.service'
import { DocumentService } from './rest/document.service'
import {
  FileStatusPhase,
  WebsocketStatusService,
} from './websocket-status.service'

@Injectable({
  providedIn: 'root',
})
export class UploadDocumentsService {
  private documentService = inject(DocumentService)
  private websocketStatusService = inject(WebsocketStatusService)
  private configService = inject(ConfigService)

  private uploadSubscriptions: Array<Subscription> = []
  private splitPdfOnUpload = false

  constructor() {
    this.configService
      .getConfig()
      .subscribe((c) => (this.splitPdfOnUpload = !!c.split_pdf_on_upload))
  }

  public setSplitPdfOnUpload(split: boolean) {
    this.splitPdfOnUpload = split
  }

  public uploadFile(file: File, splitPdfOnUpload = this.splitPdfOnUpload) {
    let formData = new FormData()
    formData.append('document', file, file.name)
    formData.append('from_webui', 'true')
    formData.append('split_pdf', splitPdfOnUpload ? 'true' : 'false')
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
