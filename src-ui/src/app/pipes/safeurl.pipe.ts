import { Pipe, PipeTransform, inject } from '@angular/core'
import { DomSanitizer } from '@angular/platform-browser'

@Pipe({
  name: 'safeUrl',
})
export class SafeUrlPipe implements PipeTransform {
  private sanitizer = inject(DomSanitizer)

  transform(url) {
    if (url == null) {
      return this.sanitizer.bypassSecurityTrustResourceUrl('')
    } else {
      return this.sanitizer.bypassSecurityTrustResourceUrl(url)
    }
  }
}
