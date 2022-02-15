import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';
import { environment } from 'src/environments/environment';
import { WebsocketConsumerStatusMessage } from '../data/websocket-consumer-status-message';

export enum FileStatusPhase {
  STARTED = 0,
  UPLOADING = 1,
  PROCESSING = 2,
  SUCCESS = 3,
  FAILED = 4
}

export const FILE_STATUS_MESSAGES = {
  "document_already_exists": $localize`Document already exists.`,
  "file_not_found": $localize`File not found.`,
  "pre_consume_script_not_found": $localize`:Pre-Consume is a term that appears like that in the documentation as well and does not need a specific translation:Pre-consume script does not exist.`,
  "pre_consume_script_error": $localize`:Pre-Consume is a term that appears like that in the documentation as well and does not need a specific translation:Error while executing pre-consume script.`,
  "post_consume_script_not_found": $localize`:Post-Consume is a term that appears like that in the documentation as well and does not need a specific translation:Post-consume script does not exist.`,
  "post_consume_script_error": $localize`:Post-Consume is a term that appears like that in the documentation as well and does not need a specific translation:Error while executing post-consume script.`,
  "new_file": $localize`Received new file.`,
  "unsupported_type": $localize`File type not supported.`,
  "parsing_document": $localize`Processing document...`,
  "generating_thumbnail": $localize`Generating thumbnail...`,
  "parse_date": $localize`Retrieving date from document...`,
  "save_document": $localize`Saving document...`,
  "finished": $localize`Finished.`
}

export class FileStatus {

  filename: string

  taskId: string

  phase: FileStatusPhase = FileStatusPhase.STARTED

  currentPhaseProgress: number

  currentPhaseMaxProgress: number

  message: string

  documentId: number

  getProgress(): number {
    switch (this.phase) {
      case FileStatusPhase.STARTED:
        return 0.0
      case FileStatusPhase.UPLOADING:
        return this.currentPhaseProgress / this.currentPhaseMaxProgress * 0.2
      case FileStatusPhase.PROCESSING:
        return (this.currentPhaseProgress / this.currentPhaseMaxProgress * 0.8) + 0.2
      case FileStatusPhase.SUCCESS:
      case FileStatusPhase.FAILED:
        return 1.0
    }
  }

  updateProgress(status: FileStatusPhase, currentProgress?: number, maxProgress?: number) {
    if (status >= this.phase) {
      this.phase = status
      if (currentProgress != null) {
        this.currentPhaseProgress = currentProgress
      }
      if (maxProgress != null) {
        this.currentPhaseMaxProgress = maxProgress
      }
    }
  }

}

@Injectable({
  providedIn: 'root'
})
export class ConsumerStatusService {

  constructor() { }

  private statusWebSocket: WebSocket

  private consumerStatus: FileStatus[] = []

  private documentDetectedSubject = new Subject<FileStatus>()
  private documentConsumptionFinishedSubject = new Subject<FileStatus>()
  private documentConsumptionFailedSubject = new Subject<FileStatus>()

  private get(taskId: string, filename?: string) {
    let status = this.consumerStatus.find(e => e.taskId == taskId) || this.consumerStatus.find(e => e.filename == filename && e.taskId == null)
    let created = false
    if (!status) {
      status = new FileStatus()
      this.consumerStatus.push(status)
      created = true
    }
    status.taskId = taskId
    status.filename = filename
    return {'status': status, 'created': created}
  }

  newFileUpload(filename: string): FileStatus {
    let status = new FileStatus()
    status.filename = filename
    this.consumerStatus.push(status)
    return status
  }

  getConsumerStatus(phase?: FileStatusPhase) {
    if (phase != null) {
      return this.consumerStatus.filter(s => s.phase == phase)
    } else {
      return this.consumerStatus
    }
  }

  getConsumerStatusNotCompleted() {
    return this.consumerStatus.filter(s => s.phase < FileStatusPhase.SUCCESS)
  }

  getConsumerStatusCompleted() {
    return this.consumerStatus.filter(s => s.phase == FileStatusPhase.FAILED || s.phase == FileStatusPhase.SUCCESS)
  }

  connect() {
    this.disconnect()

    this.statusWebSocket = new WebSocket(`${environment.webSocketProtocol}//${environment.webSocketHost}${environment.webSocketBaseUrl}status/`);
    this.statusWebSocket.onmessage = (ev) => {
      let statusMessage: WebsocketConsumerStatusMessage = JSON.parse(ev['data'])

      let statusMessageGet = this.get(statusMessage.task_id, statusMessage.filename)
      let status = statusMessageGet.status
      let created = statusMessageGet.created

      status.updateProgress(FileStatusPhase.PROCESSING, statusMessage.current_progress, statusMessage.max_progress)
      if (statusMessage.message && statusMessage.message in FILE_STATUS_MESSAGES) {
        status.message = FILE_STATUS_MESSAGES[statusMessage.message]
      } else if (statusMessage.message) {
        status.message = statusMessage.message
      }
      status.documentId = statusMessage.document_id

      if (created && statusMessage.status == 'STARTING') {
        this.documentDetectedSubject.next(status)
      }
      if (statusMessage.status == "SUCCESS") {
        status.phase = FileStatusPhase.SUCCESS
        this.documentConsumptionFinishedSubject.next(status)
      }
      if (statusMessage.status == "FAILED") {
        status.phase = FileStatusPhase.FAILED
        this.documentConsumptionFailedSubject.next(status)
      }
    }
  }

  fail(status: FileStatus, message: string) {
    status.message = message
    status.phase = FileStatusPhase.FAILED
    this.documentConsumptionFailedSubject.next(status)
  }

  disconnect() {
    if (this.statusWebSocket) {
      this.statusWebSocket.close()
      this.statusWebSocket = null
    }
  }

  dismiss(status: FileStatus) {
    let index
    if (status.taskId != null) {
      index = this.consumerStatus.findIndex(s => s.taskId == status.taskId)
    } else {
      index = this.consumerStatus.findIndex(s => s.filename == status.filename)
    }

    if (index > -1) {
      this.consumerStatus.splice(index, 1)
    }
  }

  dismissCompleted() {
    this.consumerStatus = this.consumerStatus.filter(status => status.phase != FileStatusPhase.SUCCESS)
  }

  onDocumentConsumptionFinished() {
    return this.documentConsumptionFinishedSubject
  }

  onDocumentConsumptionFailed() {
    return this.documentConsumptionFailedSubject
  }

  onDocumentDetected() {
    return this.documentDetectedSubject
  }

}
