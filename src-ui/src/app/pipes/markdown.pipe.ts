import { Pipe, PipeTransform } from '@angular/core'
import { Marked, Renderer, Tokens } from 'marked'

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
  transform(value: string | null | undefined): string {
    if (!value) return ''
    return markdown.parse(value) as string
  }
}
