import {
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http'
import { inject, Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import { CsrfService } from '../services/csrf.service'

@Injectable()
export class CsrfInterceptor implements HttpInterceptor {
  private csrfService = inject(CsrfService)

  intercept(
    request: HttpRequest<unknown>,
    next: HttpHandler
  ): Observable<HttpEvent<unknown>> {
    const csrfToken = this.csrfService.getToken()
    if (csrfToken) {
      request = request.clone({
        setHeaders: {
          'X-CSRFToken': csrfToken,
        },
      })
    }

    return next.handle(request)
  }
}
