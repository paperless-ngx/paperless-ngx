import {
  HttpErrorResponse,
  HttpHandlerFn,
  HttpRequest,
} from '@angular/common/http'
import { throwError } from 'rxjs'
import * as navUtils from '../utils/navigation'
import { createAuthExpiryInterceptor } from './auth-expiry.interceptor'

describe('withAuthExpiryInterceptor', () => {
  let interceptor: ReturnType<typeof createAuthExpiryInterceptor>
  let dateNowSpy: jest.SpiedFunction<typeof Date.now>

  beforeEach(() => {
    interceptor = createAuthExpiryInterceptor()
    dateNowSpy = jest.spyOn(Date, 'now').mockReturnValue(1000)
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('reloads when an API request returns 401', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    interceptor(
      new HttpRequest('GET', '/api/documents/'),
      failingHandler('/api/documents/', 401)
    ).subscribe({
      error: () => undefined,
    })

    expect(reloadSpy).toHaveBeenCalledTimes(1)
  })

  it('does not reload for non-401 errors', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    interceptor(
      new HttpRequest('GET', '/api/documents/'),
      failingHandler('/api/documents/', 500)
    ).subscribe({
      error: () => undefined,
    })

    expect(reloadSpy).not.toHaveBeenCalled()
  })

  it('does not reload for non-api 401 responses', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    interceptor(
      new HttpRequest('GET', '/accounts/profile/'),
      failingHandler('/accounts/profile/', 401)
    ).subscribe({
      error: () => undefined,
    })

    expect(reloadSpy).not.toHaveBeenCalled()
  })

  it('reloads only once even with multiple API 401 responses', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    const request = new HttpRequest('GET', '/api/documents/')
    const handler = failingHandler('/api/documents/', 401)

    interceptor(request, handler).subscribe({
      error: () => undefined,
    })
    interceptor(request, handler).subscribe({
      error: () => undefined,
    })

    expect(reloadSpy).toHaveBeenCalledTimes(1)
  })

  it('retries reload after cooldown for repeated API 401 responses', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    dateNowSpy
      .mockReturnValueOnce(1000)
      .mockReturnValueOnce(2500)
      .mockReturnValueOnce(3501)

    const request = new HttpRequest('GET', '/api/documents/')
    const handler = failingHandler('/api/documents/', 401)

    interceptor(request, handler).subscribe({
      error: () => undefined,
    })
    interceptor(request, handler).subscribe({
      error: () => undefined,
    })
    interceptor(request, handler).subscribe({
      error: () => undefined,
    })

    expect(reloadSpy).toHaveBeenCalledTimes(2)
  })
})

function failingHandler(url: string, status: number): HttpHandlerFn {
  return (_request) =>
    throwError(
      () =>
        new HttpErrorResponse({
          status,
          url,
        })
    )
}
