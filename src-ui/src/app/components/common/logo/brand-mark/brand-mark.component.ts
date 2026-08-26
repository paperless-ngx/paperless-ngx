import { Component } from '@angular/core'

/**
 * The paperless-ngx leaf mark, applied as an attribute on an <svg>
 */
@Component({
  selector: 'svg[pngx-brand-mark]',
  templateUrl: './brand-mark.component.html',
  host: {
    '[attr.xmlns]': "'http://www.w3.org/2000/svg'",
    '[attr.viewBox]': "'0 0 1000 1000'",
    '[attr.fill]': "'currentColor'",
    '[attr.aria-hidden]': "'true'",
  },
})
export class BrandMarkComponent {}
