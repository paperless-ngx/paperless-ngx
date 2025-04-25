import { Injectable } from '@angular/core'
import { Subject } from 'rxjs'
import { environment } from 'src/environments/environment'
import { User } from '../data/user'
import { WebsocketDocumentsDeletedMessage } from '../data/websocket-documents-deleted-message'
import { WebsocketProgressMessage } from '../data/websocket-progress-message'
import { SettingsService } from './settings.service'

export enum WebsocketStatusType {
  STATUS_UPDATE = 'status_update',
  DOCUMENTS_DELETED = 'documents_deleted',
}

// see ProgressStatusOptions in src/documents/plugins/helpers.py
export enum FileStatusPhase {
  STARTED = 0,
  UPLOADING = 1,
  WORKING = 2,
  SUCCESS = 3,
  FAILED = 4,
}

export const FILE_STATUS_MESSAGES = {
  document_already_exists: $localize`Document already exists.`,
  document_already_exists_in_trash: $localize`Document already exists. Note: existing document is in the trash.`,
  asn_already_exists: $localize`Document with ASN already exists.`,
  asn_already_exists_in_trash: $localize`Document with ASN already exists. Note: existing document is in the trash.`,
  file_not_found: $localize`File not found.`,
  pre_consume_script_not_found: $localize`:Pre-Consume is a term that appears like that in the documentation as well and does not need a specific translation:Pre-consume script does not exist.`,
  pre_consume_script_error: $localize`:Pre-Consume is a term that appears like that in the documentation as well and does not need a specific translation:Error while executing pre-consume script.`,
  post_consume_script_not_found: $localize`:Post-Consume is a term that appears like that in the documentation as well and does not need a specific translation:Post-consume script does not exist.`,
  post_consume_script_error: $localize`:Post-Consume is a term that appears like that in the documentation as well and does not need a specific translation:Error while executing post-consume script.`,
  new_file: $localize`Received new file.`,
  unsupported_type: $localize`File type not supported.`,
  parsing_document: $localize`Processing document...`,
  generating_thumbnail: $localize`Generating thumbnail...`,
  parse_date: $localize`Retrieving date from document...`,
  save_document: $localize`Saving document...`,
  finished: $localize`Finished.`,
}

export class FileStatus {
  filename: string

  taskId: string

  phase: FileStatusPhase = FileStatusPhase.STARTED

  currentPhaseProgress: number

  currentPhaseMaxProgress: number

  message: string

  documentId: number

  ownerId: number

  getProgress(): number {
    switch (this.phase) {
      case FileStatusPhase.STARTED:
        return 0.0
      case FileStatusPhase.UPLOADING:
        return (this.currentPhaseProgress / this.currentPhaseMaxProgress) * 0.2
      case FileStatusPhase.WORKING:
        return (
          (this.currentPhaseProgress / this.currentPhaseMaxProgress) * 0.8 + 0.2
        )
      case FileStatusPhase.SUCCESS:
      case FileStatusPhase.FAILED:
        return 1.0
    }
  }

  updateProgress(
    status: FileStatusPhase,
    currentProgress?: number,
    maxProgress?: number
  ) {
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
  providedIn: 'root',
})
export class WebsocketStatusService {
  constructor(private settingsService: SettingsService) {}

  private statusWebSocket: WebSocket

  private consumerStatus: FileStatus[] = []

  private documentDetectedSubject = new Subject<FileStatus>()
  private documentConsumptionFinishedSubject = new Subject<FileStatus>()
  private documentConsumptionFailedSubject = new Subject<FileStatus>()
  private documentDeletedSubject = new Subject<boolean>()

  private get(taskId: string, filename?: string) {
    let status =
      this.consumerStatus.find((e) => e.taskId == taskId) ||
      this.consumerStatus.find(
        (e) => e.filename == filename && e.taskId == null
      )
    let created = false
    if (!status) {
      status = new FileStatus()
      this.consumerStatus.push(status)
      created = true
    }
    status.taskId = taskId
    status.filename = filename
    return { status: status, created: created }
  }

  newFileUpload(filename: string): FileStatus {
    let status = new FileStatus()
    status.filename = filename
    this.consumerStatus.push(status)
    return status
  }

  getConsumerStatus(phase?: FileStatusPhase) {
    if (phase != null) {
      return this.consumerStatus.filter((s) => s.phase == phase)
    } else {
      return this.consumerStatus
    }
  }

  getConsumerStatusNotCompleted() {
    return this.consumerStatus.filter((s) => s.phase < FileStatusPhase.SUCCESS)
  }

  getConsumerStatusCompleted() {
    return this.consumerStatus.filter(
      (s) =>
        s.phase == FileStatusPhase.FAILED || s.phase == FileStatusPhase.SUCCESS
    )
  }

  connect() {
    this.disconnect()

    this.statusWebSocket = new WebSocket(
      `${environment.webSocketProtocol}//${environment.webSocketHost}${environment.webSocketBaseUrl}status/`
    )
    this.statusWebSocket.onmessage = (ev: MessageEvent) => {
      const {
        type,
        data: messageData,
      }: {
        type: WebsocketStatusType
        data: WebsocketProgressMessage | WebsocketDocumentsDeletedMessage
      } = JSON.parse(ev.data)

      switch (type) {
        case WebsocketStatusType.DOCUMENTS_DELETED:
          this.documentDeletedSubject.next(true)
          break

        case WebsocketStatusType.STATUS_UPDATE:
          this.handleProgressUpdate(messageData as WebsocketProgressMessage)
          break
      }
    }
  }

  private canViewMessage(messageData: WebsocketProgressMessage): boolean {
    // see paperless.consumers.StatusConsumer._can_view
    const user: User = this.settingsService.currentUser
    return (
      !messageData.owner_id ||
      user.is_superuser ||
      (messageData.owner_id && messageData.owner_id === user.id) ||
      (messageData.users_can_view &&
        messageData.users_can_view.includes(user.id)) ||
      (messageData.groups_can_view &&
        messageData.groups_can_view.some((groupId) =>
          user.groups?.includes(groupId)
        ))
    )
  }

  handleProgressUpdate(messageData: WebsocketProgressMessage) {
    // fallback if backend didn't restrict message
    if (!this.canViewMessage(messageData)) {
      return
    }

    let statusMessageGet = this.get(messageData.task_id, messageData.filename)
    let status = statusMessageGet.status
    let created = statusMessageGet.created

    status.updateProgress(
      FileStatusPhase.WORKING,
      messageData.current_progress,
      messageData.max_progress
    )
    if (messageData.message && messageData.message in FILE_STATUS_MESSAGES) {
      status.message = FILE_STATUS_MESSAGES[messageData.message]
    } else if (messageData.message) {
      status.message = messageData.message
    }
    status.documentId = messageData.document_id

    if (messageData.status in FileStatusPhase) {
      status.phase = FileStatusPhase[messageData.status]
    }

    switch (status.phase) {
      case FileStatusPhase.STARTED:
        if (created) this.documentDetectedSubject.next(status)
        break

      case FileStatusPhase.SUCCESS:
        this.documentConsumptionFinishedSubject.next(status)
        break

      case FileStatusPhase.FAILED:
        this.documentConsumptionFailedSubject.next(status)
        break

      default:
        break
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
      index = this.consumerStatus.findIndex((s) => s.taskId == status.taskId)
    } else {
      index = this.consumerStatus.findIndex(
        (s) => s.filename == status.filename
      )
    }

    if (index > -1) {
      this.consumerStatus.splice(index, 1)
    }
  }

  dismissCompleted() {
    this.consumerStatus = this.consumerStatus.filter(
      (status) =>
        ![FileStatusPhase.SUCCESS, FileStatusPhase.FAILED].includes(
          status.phase
        )
    )
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

  onDocumentDeleted() {
    return this.documentDeletedSubject
  }
}
