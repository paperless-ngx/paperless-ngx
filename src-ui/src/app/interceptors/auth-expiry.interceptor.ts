import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http'
import { catchError, Observable, throwError } from 'rxjs'
import { locationReload } from '../utils/navigation'

export const createAuthExpiryInterceptor = (): HttpInterceptorFn => {
  let lastReloadAttempt = Number.NEGATIVE_INFINITY

  return (
    request: HttpRequest<unknown>,
    next: HttpHandlerFn
  ): Observable<HttpEvent<unknown>> =>
    next(request).pipe(
      catchError((error: unknown) => {
        if (
          error instanceof HttpErrorResponse &&
          error.status === 401 &&
          request.url.includes('/api/')
        ) {
          const now = Date.now()
          if (now - lastReloadAttempt >= 2000) {
            lastReloadAttempt = now
            locationReload()
          }
        }

        return throwError(() => error)
      })
    )
}

export const withAuthExpiryInterceptor = createAuthExpiryInterceptor()
