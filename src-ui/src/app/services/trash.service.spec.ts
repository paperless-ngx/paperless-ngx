import { TestBed } from '@angular/core/testing'

import { TrashService } from './trash.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'

describe('TrashService', () => {
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
      `${environment.apiBaseUrl}trash/?page=1`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call correct endpoint for emptyTrash', () => {
    service.emptyTrash().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req.request.method).toEqual('POST')
    expect(req.request.body).toEqual({ action: 'empty' })

    service.emptyTrash([1, 2, 3]).subscribe()
    const req2 = httpTestingController.expectOne(
      `${environment.apiBaseUrl}trash/`
    )
    expect(req2.request.body).toEqual({
      action: 'empty',
      documents: [1, 2, 3],
    })
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
