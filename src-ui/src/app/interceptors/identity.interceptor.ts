import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http'
import { catchError, Observable, throwError } from 'rxjs'
import { environment } from 'src/environments/environment'
import { locationReload } from '../utils/navigation'

let expectedUserId: number | undefined

/** Records the user identity expected by subsequent API requests. */
export function setExpectedUserId(userId: number | undefined): void {
  expectedUserId = userId
}

/** Detects API responses made stale by an account change in another tab. */
export const withIdentityInterceptor: HttpInterceptorFn = (
  request: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> => {
  if (expectedUserId && request.url.startsWith(environment.apiBaseUrl)) {
    request = request.clone({
      setHeaders: { 'X-Paperless-User-ID': expectedUserId.toString() },
    })
  }
  return next(request).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 409 &&
        error.error?.code === 'account_session_changed'
      ) {
        locationReload()
      }
      return throwError(() => error)
    })
  )
}
