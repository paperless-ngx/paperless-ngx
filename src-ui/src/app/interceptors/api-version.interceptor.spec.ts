import {
  HttpClient,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { withApiVersionInterceptor } from './api-version.interceptor'

describe('ApiVersionInterceptor', () => {
  let httpClient: HttpClient
  let httpMock: HttpTestingController

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([withApiVersionInterceptor])),
        provideHttpClientTesting(),
      ],
    })

    httpClient = TestBed.inject(HttpClient)
    httpMock = TestBed.inject(HttpTestingController)
  })

  it('should add api version to headers', () => {
    httpClient.get('https://example.com').subscribe()
    const request = httpMock.expectOne('https://example.com')
    const header = request.request.headers['lazyUpdate'][0]

    expect(header.name).toEqual('Accept')
    expect(header.value).toEqual(
      `application/json; version=${environment.apiVersion}`
    )
    request.flush({})
  })
})
