import {
  HttpEventType,
  HttpResponse,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import WS from 'jest-websocket-mock'
import { environment } from 'src/environments/environment'
import { DocumentService } from './rest/document.service'
import { SettingsService } from './settings.service'
import {
  FILE_STATUS_MESSAGES,
  FileStatusPhase,
  WebsocketStatusService,
  WebsocketStatusType,
} from './websocket-status.service'

describe('ConsumerStatusService', () => {
  let httpTestingController: HttpTestingController
  let websocketStatusService: WebsocketStatusService
  let documentService: DocumentService
  let settingsService: SettingsService

  const server = new WS(
    `${environment.webSocketProtocol}//${environment.webSocketHost}${environment.webSocketBaseUrl}status/`,
    { jsonProtocol: true }
  )

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        WebsocketStatusService,
        DocumentService,
        SettingsService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = {
      id: 1,
      username: 'testuser',
      is_superuser: false,
    }
    websocketStatusService = TestBed.inject(WebsocketStatusService)
    documentService = TestBed.inject(DocumentService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('should update status on websocket processing progress', () => {
    const task_id = '1234'
    const status = websocketStatusService.newFileUpload('file.pdf')
    expect(status.getProgress()).toEqual(0)

    websocketStatusService.connect()

    websocketStatusService
      .onDocumentConsumptionFinished()
      .subscribe((filestatus) => {
        expect(filestatus.phase).toEqual(FileStatusPhase.SUCCESS)
      })

    websocketStatusService.onDocumentDetected().subscribe((filestatus) => {
      expect(filestatus.phase).toEqual(FileStatusPhase.STARTED)
    })

    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id,
        filename: 'file.pdf',
        current_progress: 50,
        max_progress: 100,
        document_id: 12,
        status: 'WORKING',
      },
    })

    expect(status.getProgress()).toBeCloseTo(0.6) // (0.8 * 50/100) + .2
    expect(websocketStatusService.getConsumerStatusNotCompleted()).toEqual([
      status,
    ])

    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id,
        filename: 'file.pdf',
        current_progress: 100,
        max_progress: 100,
        document_id: 12,
        status: 'SUCCESS',
        message: FILE_STATUS_MESSAGES.finished,
      },
    })

    expect(status.getProgress()).toEqual(1)
    expect(websocketStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      0
    )
    expect(websocketStatusService.getConsumerStatusCompleted()).toHaveLength(1)

    websocketStatusService.disconnect()
  })

  it('should update status on websocket failed progress', () => {
    const task_id = '1234'
    const status = websocketStatusService.newFileUpload('file.pdf')
    status.taskId = task_id
    websocketStatusService.connect()

    websocketStatusService
      .onDocumentConsumptionFailed()
      .subscribe((filestatus) => {
        expect(filestatus.phase).toEqual(FileStatusPhase.FAILED)
      })

    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id,
        filename: 'file.pdf',
        current_progress: 50,
        max_progress: 100,
        document_id: 12,
      },
    })

    expect(websocketStatusService.getConsumerStatusNotCompleted()).toEqual([
      status,
    ])

    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id,
        filename: 'file.pdf',
        current_progress: 50,
        max_progress: 100,
        document_id: 12,
        status: 'FAILED',
        message: FILE_STATUS_MESSAGES.document_already_exists,
      },
    })

    expect(websocketStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      0
    )
    expect(websocketStatusService.getConsumerStatusCompleted()).toHaveLength(1)
  })

  it('should update status on upload progress', () => {
    const task_id = '1234'
    const status = websocketStatusService.newFileUpload('file.pdf')

    documentService.uploadDocument({}).subscribe((event) => {
      if (event.type === HttpEventType.Response) {
        status.taskId = event.body['task_id']
        status.message = $localize`Upload complete, waiting...`
      } else if (event.type === HttpEventType.UploadProgress) {
        status.updateProgress(
          FileStatusPhase.UPLOADING,
          event.loaded,
          event.total
        )
      }
    })

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    req.event(
      new HttpResponse({
        body: {
          task_id,
        },
      })
    )

    req.event({
      type: HttpEventType.UploadProgress,
      loaded: 100,
      total: 300,
    })

    expect(
      websocketStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
    ).toEqual([status])
    expect(websocketStatusService.getConsumerStatus()).toEqual([status])
    expect(websocketStatusService.getConsumerStatusNotCompleted()).toEqual([
      status,
    ])

    req.event({
      type: HttpEventType.UploadProgress,
      loaded: 300,
      total: 300,
    })

    expect(status.getProgress()).toEqual(0.2) // 0.2 * 300/300
  })

  it('should support dismiss completed', () => {
    websocketStatusService.connect()
    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id: '1234',
        filename: 'file.pdf',
        current_progress: 100,
        max_progress: 100,
        document_id: 12,
        status: 'SUCCESS',
        message: 'finished',
      },
    })

    expect(websocketStatusService.getConsumerStatusCompleted()).toHaveLength(1)
    websocketStatusService.dismissCompleted()
    expect(websocketStatusService.getConsumerStatusCompleted()).toHaveLength(0)
    websocketStatusService.disconnect()
  })

  it('should support dismiss', () => {
    const task_id = '1234'
    const status = websocketStatusService.newFileUpload('file.pdf')
    status.taskId = task_id
    status.updateProgress(FileStatusPhase.UPLOADING, 50, 100)

    const status2 = websocketStatusService.newFileUpload('file2.pdf')
    status2.updateProgress(FileStatusPhase.UPLOADING, 50, 100)

    expect(
      websocketStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
    ).toEqual([status, status2])
    expect(websocketStatusService.getConsumerStatus()).toEqual([
      status,
      status2,
    ])
    expect(websocketStatusService.getConsumerStatusNotCompleted()).toEqual([
      status,
      status2,
    ])

    websocketStatusService.dismiss(status)
    expect(websocketStatusService.getConsumerStatus()).toEqual([status2])

    websocketStatusService.dismiss(status2)
    expect(websocketStatusService.getConsumerStatus()).toHaveLength(0)
  })

  it('should support fail', () => {
    const task_id = '1234'
    const status = websocketStatusService.newFileUpload('file.pdf')
    status.taskId = task_id
    status.updateProgress(FileStatusPhase.UPLOADING, 50, 100)
    expect(websocketStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      1
    )
    expect(websocketStatusService.getConsumerStatusCompleted()).toHaveLength(0)
    websocketStatusService.fail(status, 'fail')
    expect(websocketStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      0
    )
    expect(websocketStatusService.getConsumerStatusCompleted()).toHaveLength(1)
  })

  it('should notify of document created on status message without upload', () => {
    let detected = false
    websocketStatusService.onDocumentDetected().subscribe((filestatus) => {
      expect(filestatus.phase).toEqual(FileStatusPhase.STARTED)
      detected = true
    })

    websocketStatusService.connect()
    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id: '1234',
        filename: 'file.pdf',
        current_progress: 0,
        max_progress: 100,
        message: 'new_file',
        status: 'STARTED',
      },
    })

    websocketStatusService.disconnect()
    expect(detected).toBeTruthy()
  })

  it('should notify of document in progress without upload', () => {
    websocketStatusService.connect()
    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id: '1234',
        filename: 'file.pdf',
        current_progress: 50,
        max_progress: 100,
        docuement_id: 12,
        status: 'WORKING',
      },
    })

    websocketStatusService.disconnect()
    expect(websocketStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      1
    )
  })

  it('should not notify current user if document has different expected owner', () => {
    websocketStatusService.connect()
    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id: '1234',
        filename: 'file1.pdf',
        current_progress: 50,
        max_progress: 100,
        docuement_id: 12,
        owner_id: 1,
        status: 'WORKING',
      },
    })

    server.send({
      type: WebsocketStatusType.STATUS_UPDATE,
      data: {
        task_id: '5678',
        filename: 'file2.pdf',
        current_progress: 50,
        max_progress: 100,
        docuement_id: 13,
        owner_id: 2,
        status: 'WORKING',
      },
    })

    websocketStatusService.disconnect()
    expect(websocketStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      1
    )
  })

  it('should trigger deleted subject on document deleted', () => {
    let deleted = false
    websocketStatusService.onDocumentDeleted().subscribe(() => {
      deleted = true
    })

    websocketStatusService.connect()
    server.send({
      type: WebsocketStatusType.DOCUMENTS_DELETED,
      data: {
        documents: [1, 2, 3],
      },
    })

    websocketStatusService.disconnect()
    expect(deleted).toBeTruthy()
  })
})
