import { Injectable } from '@angular/core';
import {
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpInterceptor
} from '@angular/common/http';
import { Observable } from 'rxjs';
import { CookieService } from 'ngx-cookie-service';

@Injectable()
export class CsrfInterceptor implements HttpInterceptor {

  constructor(private cookieService: CookieService) {

  }

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    let csrfToken = this.cookieService.get('csrftoken')
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
