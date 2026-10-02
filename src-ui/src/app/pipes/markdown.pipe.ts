import { Pipe, PipeTransform, inject } from '@angular/core'
import { DomSanitizer, SafeHtml } from '@angular/platform-browser'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

// Renders assistant markdown as sanitized HTML safe for [innerHTML].
// - marked handles headings, lists, code blocks, tables, links, etc.
// - DOMPurify strips any HTML the model tried to inject (script, on*,
//   javascript: URLs, etc.) so the result is safe to bind.
@Pipe({
  name: 'markdown',
})
export class MarkdownPipe implements PipeTransform {
  private sanitizer = inject(DomSanitizer)

  transform(value: string | null | undefined): SafeHtml {
    if (!value) return ''
    const rawHtml = marked.parse(value, { async: false }) as string
    const cleanHtml = DOMPurify.sanitize(rawHtml, {
      USE_PROFILES: { html: true },
      // Allow explicit safe attributes that markdown renderers often emit
      ADD_ATTR: ['target', 'rel'],
    })
    return this.sanitizer.bypassSecurityTrustHtml(cleanHtml)
  }
}
