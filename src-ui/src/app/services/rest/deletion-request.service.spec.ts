import { TestBed } from '@angular/core/testing'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { DeletionRequestService } from './deletion-request.service'
import { environment } from 'src/environments/environment'

describe('DeletionRequestService', () => {
  let service: DeletionRequestService
  let httpMock: HttpTestingController

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [DeletionRequestService],
    })
    service = TestBed.inject(DeletionRequestService)
    httpMock = TestBed.inject(HttpTestingController)
  })

  afterEach(() => {
    httpMock.verify()
  })

  it('should be created', () => {
    expect(service).toBeTruthy()
  })

  it('should get pending count', () => {
    const mockResponse = { count: 5 }

    service.getPendingCount().subscribe((response) => {
      expect(response.count).toBe(5)
    })

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}deletion_requests/pending_count/`
    )
    expect(req.request.method).toBe('GET')
    req.flush(mockResponse)
  })

  it('should approve a deletion request', () => {
    const mockRequest = {
      id: 1,
      status: 'approved',
    }

    service.approve(1, 'Approved').subscribe((response) => {
      expect(response.status).toBe('approved')
    })

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}deletion_requests/1/approve/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({ review_comment: 'Approved' })
    req.flush(mockRequest)
  })

  it('should reject a deletion request', () => {
    const mockRequest = {
      id: 1,
      status: 'rejected',
    }

    service.reject(1, 'Rejected').subscribe((response) => {
      expect(response.status).toBe('rejected')
    })

    const req = httpMock.expectOne(
      `${environment.apiBaseUrl}deletion_requests/1/reject/`
    )
    expect(req.request.method).toBe('POST')
    expect(req.request.body).toEqual({ review_comment: 'Rejected' })
    req.flush(mockRequest)
  })
})
