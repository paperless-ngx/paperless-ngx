import { TestBed } from '@angular/core/testing'

import { TrashService } from './trash.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'

describe('TrashServiceService', () => {
  let service: TrashService
  let httpTestingController: HttpTestingController

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    })
    service = TestBed.inject(TrashService)
    httpTestingController = TestBed.inject(HttpTestingController)
  })

  it('should call correct endpoint for getTrash', () => {
    service.getTrash().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call correct endpoint for emptyTrash', () => {
    service.emptyTrash().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({ action: 'empty', documents: [] })
  })

  it('should call correct endpoint for restoreDocuments', () => {
    service.restoreDocuments([1, 2, 3]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({
      action: 'restore',
      documents: [1, 2, 3],
    })
  })
})
