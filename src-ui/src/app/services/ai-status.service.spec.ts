import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { AIStatus } from 'src/app/data/ai-status'
import { environment } from 'src/environments/environment'
import { AIStatusService } from './ai-status.service'

describe('AIStatusService', () => {
  let service: AIStatusService
  let httpMock: HttpTestingController

  const mockAIStatus: AIStatus = {
    active: true,
    processing: false,
    documents_scanned_today: 42,
    suggestions_applied: 15,
    pending_deletion_requests: 2,
    last_scan: '2025-11-15T12:00:00Z',
    version: '1.0.0',
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [AIStatusService],
    })
    service = TestBed.inject(AIStatusService)
    httpMock = TestBed.inject(HttpTestingController)
  })

  afterEach(() => {
    httpMock.verify()
  })

  it('should be created', () => {
    expect(service).toBeTruthy()
  })

  it('should return AI status as observable', (done) => {
    service.getStatus().subscribe((status) => {
      expect(status).toBeDefined()
      expect(status.active).toBeDefined()
      expect(status.processing).toBeDefined()
      done()
    })
  })

  it('should return current status value', () => {
    const status = service.getCurrentStatus()
    expect(status).toBeDefined()
    expect(status.active).toBeDefined()
  })

  it('should fetch AI status from backend', (done) => {
    service['fetchAIStatus']().subscribe((status) => {
      expect(status).toEqual(mockAIStatus)
      expect(service.loading).toBe(false)
      done()
    })

    const req = httpMock.expectOne(`${environment.apiBaseUrl}ai/status/`)
    expect(req.request.method).toBe('GET')
    req.flush(mockAIStatus)
  })

  it('should handle error and return mock data', (done) => {
    service['fetchAIStatus']().subscribe((status) => {
      expect(status).toBeDefined()
      expect(status.active).toBeDefined()
      expect(service.loading).toBe(false)
      done()
    })

    const req = httpMock.expectOne(`${environment.apiBaseUrl}ai/status/`)
    req.error(new ProgressEvent('error'))
  })

  it('should manually refresh status', () => {
    service.refresh()

    const req = httpMock.expectOne(`${environment.apiBaseUrl}ai/status/`)
    expect(req.request.method).toBe('GET')
    req.flush(mockAIStatus)
  })
})
