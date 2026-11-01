import {
  HttpEventType,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import {
  CHAT_METADATA_DELIMITER,
  ChatService,
  parseChatResponse,
} from './chat.service'

describe('ChatService', () => {
  let service: ChatService
  let httpMock: HttpTestingController

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        ChatService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
    service = TestBed.inject(ChatService)
    httpMock = TestBed.inject(HttpTestingController)
  })

  afterEach(() => {
    httpMock.verify()
  })

  it('should stream chat messages', (done) => {
    const documentId = 1
    const prompt = 'Hello, world!'
    const mockResponse = 'Partial response text'
    const apiUrl = `${environment.apiBaseUrl}documents/chat/`

    service.streamChat(documentId, prompt).subscribe((chunk) => {
      expect(chunk).toBe(mockResponse)
      done()
    })

    const req = httpMock.expectOne(apiUrl)
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({
      document_id: documentId,
      q: prompt,
    })

    req.event({
      type: HttpEventType.DownloadProgress,
      partialText: mockResponse,
    } as any)
  })

  it('should parse chat references from the metadata trailer', () => {
    const parsed = parseChatResponse(
      `Answer text${CHAT_METADATA_DELIMITER}{"references":[{"id":1,"title":"Document 1"}]}`
    )

    expect(parsed.content).toBe('Answer text')
    expect(parsed.references).toEqual([{ id: 1, title: 'Document 1' }])
  })

  it('should mark unavailable references without failing the complete list', () => {
    let result
    service
      .validateReferences([
        { id: 1, title: 'Old title' },
        { id: 2, title: 'Unavailable' },
      ])
      .subscribe((references) => (result = references))
    httpMock
      .expectOne((request) => request.url.endsWith('documents/1/'))
      .flush({ title: 'Current title' })
    httpMock
      .expectOne((request) => request.url.endsWith('documents/2/'))
      .flush({}, { status: 404, statusText: 'Not found' })
    expect(result[0].title).toBe('Current title')
    expect(result[0].error).toBeUndefined()
    expect(result[1].error).toContain('could not be fetched')
  })

  it('should emit the final body when the transport does not report progress', () => {
    const chunks: string[] = []
    service
      .streamChat(undefined, 'Hello')
      .subscribe((chunk) => chunks.push(chunk))
    const response = `Answer${CHAT_METADATA_DELIMITER}{"references":[{"id":42,"title":"Source"}]}`
    httpMock
      .expectOne(`${environment.apiBaseUrl}documents/chat/`)
      .flush(response)
    expect(chunks).toEqual([response])
    expect(parseChatResponse(chunks[0]).references).toEqual([
      { id: 42, title: 'Source' },
    ])
  })

  it('should hide incomplete metadata trailer from the visible content', () => {
    const parsed = parseChatResponse(
      `Answer text${CHAT_METADATA_DELIMITER}{"references"`
    )

    expect(parsed.content).toBe('Answer text')
    expect(parsed.references).toBeUndefined()
  })
})
