import {
  HttpEvent,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http'
import { inject } from '@angular/core'
import { Meta } from '@angular/platform-browser'
import { CookieService } from 'ngx-cookie-service'
import { Observable } from 'rxjs'

export const withCsrfInterceptor: HttpInterceptorFn = (
  request: HttpRequest<unknown>,
  next: HttpHandlerFn
): Observable<HttpEvent<unknown>> => {
  const cookieService: CookieService = inject(CookieService)
  const meta: Meta = inject(Meta)

  let prefix = ''
  if (meta.getTag('name=cookie_prefix')) {
    prefix = meta.getTag('name=cookie_prefix').content
  }
  let csrfToken = cookieService.get(`${prefix}csrftoken`)
  if (csrfToken) {
    request = request.clone({
      setHeaders: {
        'X-CSRFToken': csrfToken,
      },
    })
  }
  return next(request)
}
