import { Pipe, PipeTransform } from '@angular/core'
import { Marked, Renderer, Tokens } from 'marked'
import { ChatReference } from 'src/app/services/chat.service'

const ALLOWED_LINK_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])

function allowedUrl(href: string): URL | null {
  try {
    const url = new URL(href)
    return ALLOWED_LINK_PROTOCOLS.has(url.protocol) ? url : null
  } catch {
    return null
  }
}

// Treat chat content as untrusted: no raw HTML, no images, and only
// absolute links. All escaping is done by marked's default renderer, and
// Angular's sanitizer runs on top of this as well.
const renderer: Partial<Renderer> = {
  html(this: Renderer, { raw, text }: Tokens.HTML | Tokens.Tag): string {
    return this.text({ type: 'text', raw, text })
  },
  image(this: Renderer, { raw, text }: Tokens.Image): string {
    return this.text({ type: 'text', raw, text })
  },
  link(this: Renderer, token: Tokens.Link): string {
    const url = allowedUrl(token.href)
    if (!url) return this.parser.parseInline(token.tokens)
    const anchor = Renderer.prototype.link
      .call(this, token)
      .replace('<a ', '<a target="_blank" rel="noopener noreferrer nofollow" ')
    if (!url.hostname) return anchor
    const hostname = this.text({ type: 'text', raw: '', text: url.hostname })
    return `${anchor} <span class="text-muted small">(${hostname})</span>`
  },
}

const markdown = new Marked({
  async: false,
  gfm: true,
  breaks: true,
  renderer,
})

@Pipe({
  name: 'markdown',
})
export class MarkdownPipe implements PipeTransform {
  transform(
    value: string | null | undefined,
    references?: ChatReference[]
  ): string {
    if (!value) return ''
    if (references !== undefined) {
      const titles = new Map(
        references.map((reference) => [reference.id, reference])
      )
      const withCitations = new Marked({
        async: false,
        gfm: true,
        breaks: true,
        renderer,
        extensions: [
          {
            name: 'documentCitation',
            level: 'inline',
            start: (source) => source.indexOf('[[document:'),
            tokenizer(source) {
              const match = /^\[\[document:(\d+)\]\]/.exec(source)
              if (match) {
                return {
                  type: 'documentCitation',
                  raw: match[0],
                  id: +match[1],
                }
              }
            },
            renderer(token) {
              const reference = titles.get(token.id)
              const error =
                reference?.error ??
                (!reference
                  ? $localize`The model cited a document that was not in the retrieved results. This citation cannot be verified.`
                  : null)
              const title = (error ?? reference.title)
                .replace(/&/g, '&amp;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
              if (error) {
                return `<span class="chat-citation text-danger" title="${title}">[${token.id}] ⚠</span>`
              }
              return `<a href="/documents/${token.id}" class="chat-citation" title="${title}">[${token.id}]</a>`
            },
          },
        ],
      })
      return withCitations.parse(value) as string
    }
    return markdown.parse(value) as string
  }
}
