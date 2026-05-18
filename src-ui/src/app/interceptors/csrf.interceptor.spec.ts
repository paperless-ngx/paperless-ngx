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
import { Meta } from '@angular/platform-browser'
import { CookieService } from 'ngx-cookie-service'
import { withCsrfInterceptor } from './csrf.interceptor'

describe('CsrfInterceptor', () => {
  let meta: Meta
  let cookieService: CookieService
  let httpClient: HttpClient
  let httpMock: HttpTestingController

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        Meta,
        CookieService,
        provideHttpClient(withInterceptors([withCsrfInterceptor])),
        provideHttpClientTesting(),
      ],
    })

    meta = TestBed.inject(Meta)
    cookieService = TestBed.inject(CookieService)
    httpClient = TestBed.inject(HttpClient)
    httpMock = TestBed.inject(HttpTestingController)
  })

  it('should get csrf token', () => {
    meta.addTag({ name: 'cookie_prefix', content: 'ngx-' }, true)

    const cookieServiceSpy = jest.spyOn(cookieService, 'get')
    cookieServiceSpy.mockReturnValue('csrftoken')

    httpClient.get('https://example.com').subscribe()
    const request = httpMock.expectOne('https://example.com')

    expect(request.request.headers['lazyUpdate'][0]['name']).toEqual(
      'X-CSRFToken'
    )
    expect(cookieServiceSpy).toHaveBeenCalled()
    request.flush({})
  })
})
