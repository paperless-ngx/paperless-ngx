import { Pipe, PipeTransform, SecurityContext, inject } from '@angular/core'
import { DomSanitizer } from '@angular/platform-browser'
import hljs from 'highlight.js'
import { Marked } from 'marked'
import { markedHighlight } from 'marked-highlight'

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
  })
)

@Pipe({
  name: 'chatMarkdown',
})
export class ChatMarkdownPipe implements PipeTransform {
  private readonly sanitizer = inject(DomSanitizer)

  transform(value: string | null | undefined): string {
    if (!value) return ''

    const { markdown: source, math } = extractMath(value)
    const rendered = renderMathPlaceholders(
      replaceTaskCheckboxes(
        markdown.parse(source, {
          async: false,
        })
      ),
      math
    )
    return this.sanitizer.sanitize(SecurityContext.HTML, rendered) ?? ''
  }
}

interface ChatMath {
  formula: string
  display: boolean
  placeholder: string
}

function extractMath(value: string): { markdown: string; math: ChatMath[] } {
  const math: ChatMath[] = []
  const replace = (formula: string, display: boolean): string => {
    const placeholder = `\uE000chat-math-${math.length}\uE001`
    math.push({ formula, display, placeholder })
    return placeholder
  }

  return {
    markdown: value
      .replace(/\\\[([\s\S]*?)\\\]/g, (_, formula: string) =>
        replace(formula, true)
      )
      .replace(/\\\(([\s\S]*?)\\\)/g, (_, formula: string) =>
        replace(formula, false)
      )
      .replace(/\$\$([\s\S]*?)\$\$/g, (_, formula: string) =>
        replace(formula, true)
      )
      .replace(/\$([^$\n]+?)\$/g, (_, formula: string) =>
        replace(formula, false)
      ),
    math,
  }
}

function renderMathPlaceholders(value: string, math: ChatMath[]): string {
  return math.reduce(
    (rendered, item) =>
      rendered.replace(
        item.placeholder,
        `<span class="chat-math${item.display ? ' chat-math-display' : ''}" title="${encodeURIComponent(item.formula)}"></span>`
      ),
    value
  )
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
