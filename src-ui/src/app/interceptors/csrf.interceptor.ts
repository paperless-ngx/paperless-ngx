import {
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Meta } from '@angular/platform-browser'
import { CookieService } from 'ngx-cookie-service'
import { Observable } from 'rxjs'

@Injectable()
export class CsrfInterceptor implements HttpInterceptor {
  private cookieService = inject(CookieService)
  private meta = inject(Meta)

  intercept(
    request: HttpRequest<unknown>,
    next: HttpHandler
  ): Observable<HttpEvent<unknown>> {
    let prefix = ''
    if (this.meta.getTag('name=cookie_prefix')) {
      prefix = this.meta.getTag('name=cookie_prefix').content
    }
    let csrfToken = this.cookieService.get(`${prefix}csrftoken`)
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
