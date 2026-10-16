import { provideHttpClient } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { DocumentReviewService } from './document-review.service'

describe('DocumentReviewService', () => {
  let service: DocumentReviewService
  let http: HttpTestingController
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    })
    service = TestBed.inject(DocumentReviewService)
    http = TestBed.inject(HttpTestingController)
  })
  afterEach(() => http.verify())

  it('uses the existing document API path', () => {
    service.get(10).subscribe()
    http.expectOne(`${environment.apiBaseUrl}documents/10/review/`).flush({})
  })

  it('posts the explicit action contract', () => {
    const payload = {
      action: 'submit' as const,
      reviewer: 2,
      expected_revision: 0,
      request_id: 'key',
    }
    service.mutate(10, payload).subscribe()
    const request = http.expectOne(
      `${environment.apiBaseUrl}documents/10/review/`
    )
    expect(request.request.method).toBe('POST')
    expect(request.request.body).toEqual(payload)
    request.flush({})
  })

  it('sends queue filters and pagination', () => {
    service.queue('pending', 2, 3).subscribe()
    const request = http.expectOne((request) =>
      request.url.endsWith('review_queue/')
    )
    expect(request.request.params.get('state')).toBe('pending')
    expect(request.request.params.get('reviewer')).toBe('2')
    expect(request.request.params.get('page')).toBe('3')
    expect(request.request.params.get('page_size')).toBe('20')
    request.flush({ count: 0, results: [] })
  })

  it('omits optional empty queue filters', () => {
    service.queue('', null).subscribe()
    const request = http.expectOne((request) =>
      request.url.endsWith('review_queue/')
    )
    expect(request.request.params.has('state')).toBe(false)
    expect(request.request.params.has('reviewer')).toBe(false)
    request.flush({ count: 0, results: [] })
  })
})
