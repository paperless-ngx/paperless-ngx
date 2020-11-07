import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

export interface FileStatus {
  filename?: string
  current_progress?: number
  max_progress?: number
  status?: string
  message?: string
  document_id?: number
}

@Injectable({
  providedIn: 'root'
})
export class ConsumerStatusService {

  constructor() { }

  private statusWebSocked: WebSocket

  consumerStatus: FileStatus[] = []
  private documentConsumptionFinishedSubject = new Subject<FileStatus>()
  private documentConsumptionFailedSubject = new Subject<FileStatus>()

  connect() {
    this.disconnect()
    this.statusWebSocked = new WebSocket("ws://localhost:8000/ws/status/");
    this.statusWebSocked.onmessage = (ev) => {
      let statusUpdate: FileStatus = JSON.parse(ev['data'])

      let index = this.consumerStatus.findIndex(fs => fs.filename == statusUpdate.filename)
      if (index > -1) {
        this.consumerStatus[index] = statusUpdate
      } else {
        this.consumerStatus.push(statusUpdate)
      }

      if (statusUpdate.status == "SUCCESS") {
        this.documentConsumptionFinishedSubject.next(statusUpdate)
      }
      if (statusUpdate.status == "FAILED") {
        this.documentConsumptionFailedSubject.next(statusUpdate)
      }
    }
  }

  disconnect() {
    if (this.statusWebSocked) {
      this.statusWebSocked.close()
      this.statusWebSocked = null
    }
  }

  dismiss(status: FileStatus) {
    let index = this.consumerStatus.findIndex(s => s.filename == status.filename)

    if (index > -1) {
      this.consumerStatus.splice(index, 1)
    }
  }

  onDocumentConsumptionFinished() {
    return this.documentConsumptionFinishedSubject
  }

  onDocumentConsumptionFailed() {
    return this.documentConsumptionFailedSubject
  }

}
