import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { environment } from 'src/environments/environment'
import { RemoteVersionService } from './remote-version.service'

let httpTestingController: HttpTestingController
let service: RemoteVersionService
let subscription: Subscription
const endpoint = 'remote_version'

describe('RemoteVersionService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [],
      providers: [
        RemoteVersionService,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(RemoteVersionService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })

  it('should call correct api endpoint on update check', () => {
    subscription = service.checkForUpdates().subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/`
    )
    expect(req.request.method).toEqual('GET')
  })
})
