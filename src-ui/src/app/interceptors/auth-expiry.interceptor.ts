import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http'
import { Injectable } from '@angular/core'
import { catchError, Observable, throwError } from 'rxjs'
import { locationReload } from '../utils/navigation'

@Injectable()
export class AuthExpiryInterceptor implements HttpInterceptor {
  private lastReloadAttempt = Number.NEGATIVE_INFINITY

  intercept(
    request: HttpRequest<unknown>,
    next: HttpHandler
  ): Observable<HttpEvent<unknown>> {
    return next.handle(request).pipe(
      catchError((error: unknown) => {
        if (
          error instanceof HttpErrorResponse &&
          error.status === 401 &&
          request.url.includes('/api/')
        ) {
          const now = Date.now()
          if (now - this.lastReloadAttempt >= 2000) {
            this.lastReloadAttempt = now
            locationReload()
          }
        }

        return throwError(() => error)
      })
    )
  }
}
