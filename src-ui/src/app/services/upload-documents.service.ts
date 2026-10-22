import { HttpEventType } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Subject, Subscription } from 'rxjs'
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

  private uploadSubscriptions: Array<Subscription> = []

  private readonly uploadsStartedSubject = new Subject<File[]>()

  public uploadFiles(files: Iterable<File>) {
    const started: File[] = []
    for (const file of files) {
      this.uploadFile(file)
      started.push(file)
    }
    if (started.length) this.uploadsStartedSubject.next(started)
  }

  public onUploadsStarted() {
    return this.uploadsStartedSubject.asObservable()
  }

  public uploadFile(file: File) {
    let formData = new FormData()
    formData.append('document', file, file.name)
    formData.append('from_webui', 'true')
    let status = this.websocketStatusService.newFileUpload(file.name)

    status.message = $localize`Connecting...`
    this.websocketStatusService.statusChanged()

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
            this.websocketStatusService.statusChanged()
          } else if (event.type == HttpEventType.Response) {
            status.taskId = event.body['task_id'] ?? event.body.toString()
            status.message = $localize`Upload complete, waiting...`
            this.websocketStatusService.statusChanged()
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
