import { HttpEvent, HttpRequest } from '@angular/common/http'
import { TestBed } from '@angular/core/testing'
import { of } from 'rxjs'
import { environment } from 'src/environments/environment'
import { ApiVersionInterceptor } from './api-version.interceptor'

describe('ApiVersionInterceptor', () => {
  let interceptor: ApiVersionInterceptor

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ApiVersionInterceptor],
    })

    interceptor = TestBed.inject(ApiVersionInterceptor)
  })

  it('should add api version to headers', () => {
    interceptor.intercept(new HttpRequest('GET', 'https://example.com'), {
      handle: (request) => {
        const header = request.headers['lazyUpdate'][0]
        expect(header.name).toEqual('Accept')
        expect(header.value).toEqual(
          `application/json; version=${environment.apiVersion}`
        )
        return of({} as HttpEvent<any>)
      },
    })
  })
})
