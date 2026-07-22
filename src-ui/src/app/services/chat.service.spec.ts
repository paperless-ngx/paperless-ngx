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

  it('should hide incomplete metadata trailer from the visible content', () => {
    const parsed = parseChatResponse(
      `Answer text${CHAT_METADATA_DELIMITER}{"references"`
    )

    expect(parsed.content).toBe('Answer text')
    expect(parsed.references).toBeUndefined()
  })
})
