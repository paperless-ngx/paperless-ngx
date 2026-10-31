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

// Treat markdown content as untrusted: no raw HTML or images. All escaping is
// done by marked's default renderer, and Angular's sanitizer runs on top.
const sharedRenderer: Partial<Renderer> = {
  html(this: Renderer, { raw, text }: Tokens.HTML | Tokens.Tag): string {
    return this.text({ type: 'text', raw, text })
  },
  image(this: Renderer, { raw, text }: Tokens.Image): string {
    return this.text({ type: 'text', raw, text })
  },
}

function renderLink(
  this: Renderer,
  token: Tokens.Link,
  includeHostname: boolean
): string {
  const url = allowedUrl(token.href)
  if (!url) return this.parser.parseInline(token.tokens)
  const anchor = Renderer.prototype.link
    .call(this, token)
    .replace('<a ', '<a target="_blank" rel="noopener noreferrer nofollow" ')
  if (!includeHostname || !url.hostname) return anchor
  const hostname = this.text({ type: 'text', raw: '', text: url.hostname })
  return `${anchor} <span class="text-muted small">(${hostname})</span>`
}

const chatMarkdown = new Marked({
  async: false,
  gfm: true,
  breaks: true,
  renderer: {
    ...sharedRenderer,
    link(this: Renderer, token: Tokens.Link): string {
      return renderLink.call(this, token, true)
    },
  },
})

const documentMarkdown = new Marked({
  async: false,
  gfm: true,
  breaks: false,
  renderer: {
    ...sharedRenderer,
    link(this: Renderer, token: Tokens.Link): string {
      return renderLink.call(this, token, false)
    },
    checkbox(this: Renderer, { checked }: Tokens.Checkbox): string {
      return checked ? '☑ ' : '☐ '
    },
  },
})

@Pipe({
  name: 'markdown',
})
export class MarkdownPipe implements PipeTransform {
  transform(
    value: string | null | undefined,
    mode: 'chat' | 'document' = 'chat'
  ): string {
    if (!value) return ''
    const markdown = mode === 'document' ? documentMarkdown : chatMarkdown
    return markdown.parse(value) as string
  }
}
