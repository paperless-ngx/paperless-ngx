import { Injectable } from '@angular/core'
import { Meta } from '@angular/platform-browser'
import { CookieService } from 'ngx-cookie-service' // Assuming you're using this

@Injectable({ providedIn: 'root' })
export class CsrfService {
  constructor(
    private cookieService: CookieService,
    private meta: Meta
  ) {}

  public getCookiePrefix(): string {
    let prefix = ''
    if (this.meta.getTag('name=cookie_prefix')) {
      prefix = this.meta.getTag('name=cookie_prefix').content
    }
    return prefix
  }

  public getToken(): string {
    return this.cookieService.get(`${this.getCookiePrefix()}csrftoken`)
  }
}
