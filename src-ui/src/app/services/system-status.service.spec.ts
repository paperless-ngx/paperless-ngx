import { TestBed } from '@angular/core/testing'

import { SystemStatusService } from './system-status.service'
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'

describe('SystemStatusService', () => {
  let httpTestingController: HttpTestingController
  let service: SystemStatusService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SystemStatusService],
      imports: [HttpClientTestingModule],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(SystemStatusService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('calls get status endpoint', () => {
    service.get().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}status/`
    )
    expect(req.request.method).toEqual('GET')
  })
})
