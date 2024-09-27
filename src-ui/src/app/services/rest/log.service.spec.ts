import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { LogService } from './log.service'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'

let httpTestingController: HttpTestingController
let service: LogService
let subscription: Subscription
const endpoint = 'logs'

describe('LogService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        LogService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(LogService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('should call correct api endpoint on logs list', () => {
    subscription = service.list().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/`
    )
    expect(req.request.method).toEqual('GET')
  })

  it('should call correct api endpoint on logs get', () => {
    const id: string = 'mail'
    subscription = service.get(id).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${id}/`
    )
    expect(req.request.method).toEqual('GET')
  })
})
