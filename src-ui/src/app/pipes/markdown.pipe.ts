import { Pipe, PipeTransform } from '@angular/core'
import { Marked, Renderer, Tokens } from 'marked'

const ALLOWED_LINK_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])

function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function safeHref(href: string): string | null {
  try {
    const url = new URL(href)
    return ALLOWED_LINK_PROTOCOLS.has(url.protocol) ? url.href : null
  } catch {
    return null
  }
}

// Treat chat content as untrusted: no raw HTML, no images, and only
// absolute links. Angular sanitizer runs on top of this as well.
const renderer: Partial<Renderer> = {
  html({ text }: Tokens.HTML | Tokens.Tag): string {
    return escapeHtml(text)
  },
  image({ text }: Tokens.Image): string {
    return escapeHtml(text)
  },
  link(this: Renderer, { href, title, tokens }: Tokens.Link): string {
    const text = this.parser.parseInline(tokens)
    const url = safeHref(href)
    if (!url) return text
    const titleAttr = title ? ` title="${escapeHtml(title)}"` : ''
    const hostname = new URL(url).hostname
    const hostnameLabel = hostname
      ? ` <span class="text-muted small">(${escapeHtml(hostname)})</span>`
      : ''
    return `<a href="${escapeHtml(url)}"${titleAttr} target="_blank" rel="noopener noreferrer nofollow">${text}</a>${hostnameLabel}`
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
