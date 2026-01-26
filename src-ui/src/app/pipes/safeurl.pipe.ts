import { Pipe, PipeTransform, inject } from '@angular/core'
import { DomSanitizer } from '@angular/platform-browser'
import { environment } from 'src/environments/environment'

@Pipe({
  name: 'safeUrl',
})
export class SafeUrlPipe implements PipeTransform {
  private sanitizer = inject(DomSanitizer)

  transform(url: string | null) {
    if (!url) return this.sanitizer.bypassSecurityTrustResourceUrl('')
    try {
      const parsed = new URL(url, window.location.origin)
      const allowedOrigins = new Set([
        window.location.origin,
        new URL(environment.apiBaseUrl).origin,
      ])
      const isHttp = ['http:', 'https:'].includes(parsed.protocol)
      const originAllowed = allowedOrigins.has(parsed.origin)

      if (!isHttp || !originAllowed) {
        return this.sanitizer.bypassSecurityTrustResourceUrl('')
      }
      return this.sanitizer.bypassSecurityTrustResourceUrl(parsed.toString())
    } catch {
      return this.sanitizer.bypassSecurityTrustResourceUrl('')
    }
  }
}
