import { TestBed } from '@angular/core/testing'
import { UploadDocumentsService } from './upload-documents.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'
import { HttpEventType, HttpResponse } from '@angular/common/http'
import {
  ConsumerStatusService,
  FileStatusPhase,
} from './consumer-status.service'

describe('UploadDocumentsService', () => {
  let httpTestingController: HttpTestingController
  let uploadDocumentsService: UploadDocumentsService
  let consumerStatusService: ConsumerStatusService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [UploadDocumentsService, ConsumerStatusService],
      imports: [HttpClientTestingModule],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    consumerStatusService = TestBed.inject(ConsumerStatusService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('calls post_document api endpoint on upload', () => {
    const fileEntry = {
      name: 'file.pdf',
      isDirectory: false,
      isFile: true,
      file: (callback) => {
        return callback(
          new File(
            [new Blob(['testing'], { type: 'application/pdf' })],
            'file.pdf'
          )
        )
      },
    }
    uploadDocumentsService.uploadFiles([
      {
        relativePath: 'path/to/file.pdf',
        fileEntry,
      },
    ])
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/post_document/`
    )
    expect(req.request.method).toEqual('POST')

    req.flush('123-456')
  })

  it('updates progress during upload and failure', () => {
    const fileEntry = {
      name: 'file.pdf',
      isDirectory: false,
      isFile: true,
      file: (callback) => {
        return callback(
          new File(
            [new Blob(['testing'], { type: 'application/pdf' })],
            'file.pdf'
          )
        )
      },
    }
    uploadDocumentsService.uploadFiles([
      {
        relativePath: 'path/to/file.pdf',
        fileEntry,
      },
    ])

    expect(consumerStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      1
    )
    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
    ).toHaveLength(0)

    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    req.event({
      type: HttpEventType.UploadProgress,
      loaded: 100,
      total: 300,
    })

    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
    ).toHaveLength(1)
  })

  it('updates progress on failure', () => {
    const fileEntry = {
      name: 'file.pdf',
      isDirectory: false,
      isFile: true,
      file: (callback) => {
        return callback(
          new File(
            [new Blob(['testing'], { type: 'application/pdf' })],
            'file.pdf'
          )
        )
      },
    }
    uploadDocumentsService.uploadFiles([
      {
        relativePath: 'path/to/file.pdf',
        fileEntry,
      },
    ])

    let req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.FAILED)
    ).toHaveLength(0)

    req.flush(
      {},
      {
        status: 400,
        statusText: 'failed',
      }
    )

    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.FAILED)
    ).toHaveLength(1)

    uploadDocumentsService.uploadFiles([
      {
        relativePath: 'path/to/file.pdf',
        fileEntry,
      },
    ])

    req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    req.flush(
      {},
      {
        status: 500,
        statusText: 'failed',
      }
    )

    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.FAILED)
    ).toHaveLength(2)
  })
})
