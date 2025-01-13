import { TestBed } from '@angular/core/testing'

import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { environment } from 'src/environments/environment'
import { SystemStatusService } from './system-status.service'

describe('SystemStatusService', () => {
  let httpTestingController: HttpTestingController
  let service: SystemStatusService

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        SystemStatusService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
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
