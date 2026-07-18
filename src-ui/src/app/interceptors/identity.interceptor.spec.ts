import {
  HttpErrorResponse,
  HttpHandlerFn,
  HttpRequest,
  HttpResponse,
} from '@angular/common/http'
import { of, throwError } from 'rxjs'
import { environment } from 'src/environments/environment'
import * as navUtils from '../utils/navigation'
import {
  setExpectedUserId,
  withIdentityInterceptor,
} from './identity.interceptor'

describe('withIdentityInterceptor', () => {
  afterEach(() => {
    setExpectedUserId(undefined)
    jest.restoreAllMocks()
  })

  it('sends the initialized user id with API requests', () => {
    setExpectedUserId(42)
    const handler = jest.fn((request: HttpRequest<unknown>) =>
      of(new HttpResponse({ body: request.headers }))
    )

    withIdentityInterceptor(
      new HttpRequest('GET', `${environment.apiBaseUrl}documents/`),
      handler
    ).subscribe()

    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({
        headers: expect.objectContaining({}),
      })
    )
    expect(handler.mock.calls[0][0].headers.get('X-Paperless-User-ID')).toBe(
      '42'
    )
  })

  it('does not add the user id to non-API requests', () => {
    setExpectedUserId(42)
    const handler = jest.fn((request: HttpRequest<unknown>) =>
      of(new HttpResponse({ body: request.headers }))
    )

    withIdentityInterceptor(
      new HttpRequest('GET', '/accounts/login/'),
      handler
    ).subscribe()

    expect(
      handler.mock.calls[0][0].headers.has('X-Paperless-User-ID')
    ).toBeFalsy()
  })

  it('does not expose the user id to external API-like URLs', () => {
    setExpectedUserId(42)
    const handler = jest.fn((request: HttpRequest<unknown>) =>
      of(new HttpResponse({ body: request.headers }))
    )

    withIdentityInterceptor(
      new HttpRequest('GET', 'https://example.com/api/documents/'),
      handler
    ).subscribe()

    expect(
      handler.mock.calls[0][0].headers.has('X-Paperless-User-ID')
    ).toBeFalsy()
  })

  it('reloads when the server rejects a stale account tab', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    withIdentityInterceptor(
      new HttpRequest('GET', '/api/documents/'),
      staleAccountHandler()
    ).subscribe({ error: () => undefined })

    expect(reloadSpy).toHaveBeenCalledTimes(1)
  })
})

function staleAccountHandler(): HttpHandlerFn {
  return () =>
    throwError(
      () =>
        new HttpErrorResponse({
          status: 409,
          error: { code: 'account_session_changed' },
        })
    )
}
