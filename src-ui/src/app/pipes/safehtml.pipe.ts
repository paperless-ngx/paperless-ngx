import { Pipe, PipeTransform, inject } from '@angular/core'
import { DomSanitizer } from '@angular/platform-browser'

@Pipe({
  name: 'safeHtml',
})
export class SafeHtmlPipe implements PipeTransform {
  private sanitizer = inject(DomSanitizer)

  transform(html) {
    return this.sanitizer.bypassSecurityTrustHtml(html)
  }
}
