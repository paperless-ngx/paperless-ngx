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
  private reloadTriggered = false

  intercept(
    request: HttpRequest<unknown>,
    next: HttpHandler
  ): Observable<HttpEvent<unknown>> {
    return next.handle(request).pipe(
      catchError((error: unknown) => {
        if (
          !this.reloadTriggered &&
          error instanceof HttpErrorResponse &&
          error.status === 401 &&
          request.url.includes('/api/')
        ) {
          this.reloadTriggered = true
          locationReload()
        }

        return throwError(() => error)
      })
    )
  }
}
