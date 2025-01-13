import { HttpEvent, HttpRequest } from '@angular/common/http'
import { TestBed } from '@angular/core/testing'
import { Meta } from '@angular/platform-browser'
import { CookieService } from 'ngx-cookie-service'
import { of } from 'rxjs'
import { CsrfInterceptor } from './csrf.interceptor'

describe('CsrfInterceptor', () => {
  let interceptor: CsrfInterceptor
  let meta: Meta
  let cookieService: CookieService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [CsrfInterceptor, Meta, CookieService],
    })

    meta = TestBed.inject(Meta)
    cookieService = TestBed.inject(CookieService)
    interceptor = TestBed.inject(CsrfInterceptor)
  })

  it('should get csrf token', () => {
    meta.addTag({ name: 'cookie_prefix', content: 'ngx-' }, true)
    const cookieServiceSpy = jest.spyOn(cookieService, 'get')
    cookieServiceSpy.mockReturnValue('csrftoken')
    interceptor.intercept(new HttpRequest('GET', 'https://example.com'), {
      handle: (request) => {
        expect(request.headers['lazyUpdate'][0]['name']).toEqual('X-CSRFToken')
        return of({} as HttpEvent<any>)
      },
    })
    expect(cookieServiceSpy).toHaveBeenCalled()
  })
})
