import { TestBed } from '@angular/core/testing'
import { UploadDocumentsService } from './upload-documents.service'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'
import {
  HttpEventType,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http'
import {
  ConsumerStatusService,
  FileStatusPhase,
} from './consumer-status.service'

const files = [
  {
    lastModified: 1693349892540,
    lastModifiedDate: new Date(),
    name: 'file1.pdf',
    size: 386,
    type: 'application/pdf',
  },
  {
    lastModified: 1695618533892,
    lastModifiedDate: new Date(),
    name: 'file2.pdf',
    size: 358265,
    type: 'application/pdf',
  },
]

const fileList = {
  item: (x) => {
    return new File(
      [new Blob(['testing'], { type: files[x].type })],
      files[x].name
    )
  },
  length: files.length,
} as unknown as FileList

describe('UploadDocumentsService', () => {
  let httpTestingController: HttpTestingController
  let uploadDocumentsService: UploadDocumentsService
  let consumerStatusService: ConsumerStatusService

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        UploadDocumentsService,
        ConsumerStatusService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    consumerStatusService = TestBed.inject(ConsumerStatusService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('calls post_document api endpoint on upload', () => {
    uploadDocumentsService.uploadFiles(fileList)
    const req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )
    expect(req[0].request.method).toEqual('POST')

    req[0].flush('123-456')
  })

  it('updates progress during upload and failure', () => {
    uploadDocumentsService.uploadFiles(fileList)

    expect(consumerStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      2
    )
    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
    ).toHaveLength(0)

    const req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    req[0].event({
      type: HttpEventType.UploadProgress,
      loaded: 100,
      total: 300,
    })

    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
    ).toHaveLength(1)
  })

  it('updates progress on failure', () => {
    uploadDocumentsService.uploadFiles(fileList)

    let req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.FAILED)
    ).toHaveLength(0)

    req[0].flush(
      {},
      {
        status: 400,
        statusText: 'failed',
      }
    )

    expect(
      consumerStatusService.getConsumerStatus(FileStatusPhase.FAILED)
    ).toHaveLength(1)

    uploadDocumentsService.uploadFiles(fileList)

    req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    req[0].flush(
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

  it('accepts files via drag and drop', () => {
    const uploadSpy = jest.spyOn(
      UploadDocumentsService.prototype as any,
      'uploadFile'
    )
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
    uploadDocumentsService.onNgxFileDrop([
      {
        relativePath: 'path/to/file.pdf',
        fileEntry,
      },
    ])
    expect(uploadSpy).toHaveBeenCalled()

    let req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )
  })
})
