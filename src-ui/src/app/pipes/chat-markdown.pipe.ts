import { Pipe, PipeTransform, inject } from '@angular/core'
import { DomSanitizer, SafeHtml } from '@angular/platform-browser'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import { Marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import markedKatex from 'marked-katex-extension'

const markdown = new Marked(
  {
    async: false,
    breaks: true,
    gfm: true,
  },
  markedHighlight({
    emptyLangClass: 'hljs',
    langPrefix: 'hljs language-',
    highlight(code, language) {
      const supportedLanguage = hljs.getLanguage(language)
        ? language
        : 'plaintext'
      return hljs.highlight(code, { language: supportedLanguage }).value
    },
  }),
  markedKatex({
    nonStandard: true,
    throwOnError: false,
  })
)

@Pipe({
  name: 'chatMarkdown',
})
export class ChatMarkdownPipe implements PipeTransform {
  private sanitizer = inject(DomSanitizer)

  transform(value: string | null | undefined): SafeHtml | string {
    if (!value) return ''

    const rendered = replaceTaskCheckboxes(
      markdown.parse(normalizeMathDelimiters(value), {
        async: false,
      })
    )
    const sanitized = DOMPurify.sanitize(rendered, {
      ADD_ATTR: ['align', 'rel', 'target'],
      USE_PROFILES: { html: true, mathMl: true },
    })
    return this.sanitizer.bypassSecurityTrustHtml(sanitized)
  }
}

function normalizeMathDelimiters(value: string): string {
  return value
    .replace(
      /\\\[([\s\S]*?)\\\]/g,
      (_, formula: string) => `\n$$\n${formula}\n$$\n`
    )
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, formula: string) => `$${formula}$`)
}

function replaceTaskCheckboxes(value: string): string {
  return value.replace(
    /<li>(\s*)(<input\b(?=[^>]*\btype="checkbox")(?=[^>]*\bdisabled)[^>]*>)/gi,
    (_, whitespace: string, input: string) => {
      const checked = /\bchecked(?:\s|=|>)/i.test(input)
      const label = checked ? 'Completed' : 'Not completed'
      const symbol = checked ? '✓' : ''
      return `<li class="chat-task-item">${whitespace}<span class="chat-task-checkbox${checked ? ' checked' : ''}" role="img" aria-label="${label}">${symbol}</span>`
    }
  )
}
