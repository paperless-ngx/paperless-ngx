import { HttpErrorResponse, HttpRequest } from '@angular/common/http'
import { TestBed } from '@angular/core/testing'
import { throwError } from 'rxjs'
import * as navUtils from '../utils/navigation'
import { AuthExpiryInterceptor } from './auth-expiry.interceptor'

describe('AuthExpiryInterceptor', () => {
  let interceptor: AuthExpiryInterceptor

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AuthExpiryInterceptor],
    })

    interceptor = TestBed.inject(AuthExpiryInterceptor)
  })

  it('reloads when an API request returns 401', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    interceptor
      .intercept(new HttpRequest('GET', '/api/documents/'), {
        handle: (_request) =>
          throwError(
            () =>
              new HttpErrorResponse({
                status: 401,
                url: '/api/documents/',
              })
          ),
      })
      .subscribe({
        error: () => undefined,
      })

    expect(reloadSpy).toHaveBeenCalledTimes(1)
  })

  it('does not reload for non-401 errors', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    interceptor
      .intercept(new HttpRequest('GET', '/api/documents/'), {
        handle: (_request) =>
          throwError(
            () =>
              new HttpErrorResponse({
                status: 500,
                url: '/api/documents/',
              })
          ),
      })
      .subscribe({
        error: () => undefined,
      })

    expect(reloadSpy).not.toHaveBeenCalled()
  })

  it('does not reload for non-api 401 responses', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    interceptor
      .intercept(new HttpRequest('GET', '/accounts/profile/'), {
        handle: (_request) =>
          throwError(
            () =>
              new HttpErrorResponse({
                status: 401,
                url: '/accounts/profile/',
              })
          ),
      })
      .subscribe({
        error: () => undefined,
      })

    expect(reloadSpy).not.toHaveBeenCalled()
  })

  it('reloads only once even with multiple API 401 responses', () => {
    const reloadSpy = jest
      .spyOn(navUtils, 'locationReload')
      .mockImplementation(() => {})

    const request = new HttpRequest('GET', '/api/documents/')
    const handler = {
      handle: (_request) =>
        throwError(
          () =>
            new HttpErrorResponse({
              status: 401,
              url: '/api/documents/',
            })
        ),
    }

    interceptor.intercept(request, handler).subscribe({
      error: () => undefined,
    })
    interceptor.intercept(request, handler).subscribe({
      error: () => undefined,
    })

    expect(reloadSpy).toHaveBeenCalledTimes(1)
  })
})
