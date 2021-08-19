import { Injectable } from '@angular/core';
import {
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptor
} from '@angular/common/http';
import { Observable } from 'rxjs';
import { CookieService } from 'ngx-cookie-service';
import { Meta } from '@angular/platform-browser';

@Injectable()
export class CsrfInterceptor implements HttpInterceptor {

  constructor(private cookieService: CookieService, private meta: Meta) {

  }

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    let prefix = ""
    if (this.meta.getTag('name=cookie_prefix')) {
      prefix = this.meta.getTag('name=cookie_prefix').content
    }
    let csrfToken = this.cookieService.get(`${prefix?prefix:''}csrftoken`)
    if (csrfToken) {
     request = request.clone({
        setHeaders: {
          'X-CSRFToken': csrfToken
        }
      })
    }

    return next.handle(request);
  }
}
