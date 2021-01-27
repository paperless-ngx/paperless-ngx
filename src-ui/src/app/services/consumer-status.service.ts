import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';
import { WebsocketConsumerStatusMessage } from '../data/websocket-consumer-status-message';

export enum FileStatusPhase {
  STARTED = 0,
  UPLOADING = 1,
  PROCESSING = 2,
  SUCCESS = 3,
  FAILED = 4
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

  private statusWebSocked: WebSocket

  private consumerStatus: FileStatus[] = []


  private documentConsumptionFinishedSubject = new Subject<FileStatus>()
  private documentConsumptionFailedSubject = new Subject<FileStatus>()

  private get(taskId: string, filename?: string) {
    let status = this.consumerStatus.find(e => e.taskId == taskId) || this.consumerStatus.find(e => e.filename == filename && e.taskId == null)
    if (!status) {
      status = new FileStatus()
      this.consumerStatus.push(status)
    }
    status.taskId = taskId
    status.filename = filename
    return status
  }

  newFileUpload(filename: string): FileStatus {
    let status = new FileStatus()
    status.filename = filename
    this.consumerStatus.push(status)
    return status
  }

  getConsumerStatus(phase?: FileStatusPhase) {
    if (phase) {
      return this.consumerStatus.filter(s => s.phase == phase)
    } else {
      return this.consumerStatus
    }
  }

  connect() {
    this.disconnect()
    this.statusWebSocked = new WebSocket("ws://localhost:8000/ws/status/");
    this.statusWebSocked.onmessage = (ev) => {
      let statusMessage: WebsocketConsumerStatusMessage = JSON.parse(ev['data'])

      let status = this.get(statusMessage.task_id, statusMessage.filename)
      status.updateProgress(FileStatusPhase.PROCESSING, statusMessage.current_progress, statusMessage.max_progress)
      status.message = statusMessage.message
      status.documentId = statusMessage.document_id

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

  dismissAll() {
    this.consumerStatus = this.consumerStatus.filter(status => status.phase < FileStatusPhase.SUCCESS)
  }

  onDocumentConsumptionFinished() {
    return this.documentConsumptionFinishedSubject
  }

  onDocumentConsumptionFailed() {
    return this.documentConsumptionFailedSubject
  }

}
