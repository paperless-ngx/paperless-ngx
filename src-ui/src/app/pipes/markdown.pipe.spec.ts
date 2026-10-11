import { MarkdownPipe } from './markdown.pipe'

describe('MarkdownPipe', () => {
  const pipe = new MarkdownPipe()

  it('should return empty string for empty input', () => {
    expect(pipe.transform(null)).toEqual('')
    expect(pipe.transform(undefined)).toEqual('')
    expect(pipe.transform('')).toEqual('')
  })

  it('should render basic markdown', () => {
    const html = pipe.transform(
      '**bold** _em_ `code`\n\n- one\n- two\n\n| a | b |\n|---|---|\n| 1 | 2 |'
    )
    expect(html).toContain('<strong>bold</strong>')
    expect(html).toContain('<em>em</em>')
    expect(html).toContain('<code>code</code>')
    expect(html).toContain('<li>one</li>')
    expect(html).toContain('<table>')
  })

  it('should escape raw html', () => {
    const html = pipe.transform(
      'hi <img src=x onerror="alert(1)"> <b>x</b>\n\n<script>alert(1)</script>'
    )
    expect(html).not.toContain('<img')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('<b>')
    expect(html).toContain('&lt;script&gt;')
  })

  it('should not render images', () => {
    const html = pipe.transform(
      '![secret](https://otherdomain.example/x.png?d=1)'
    )
    expect(html).not.toContain('<img')
    expect(html).not.toContain('otherdomain.example')
    expect(html).toContain('secret')
  })

  it('should render safe links with target and rel', () => {
    const html = pipe.transform('[docs](https://docs.paperless-ngx.com "Docs")')
    expect(html).toContain(
      '<a target="_blank" rel="noopener noreferrer nofollow" href="https://docs.paperless-ngx.com" title="Docs">docs</a>'
    )
    expect(pipe.transform('[mail](mailto:a@b.c)')).toContain(
      'href="mailto:a@b.c"'
    )
  })

  it('should drop unsafe or relative links but keep their text', () => {
    for (const href of [
      'javascript:alert(1)',
      'JaVaScRiPt:alert(1)',
      'data:text/html,<script>alert(1)</script>',
      'vbscript:msgbox',
      '/api/documents/',
    ]) {
      const html = pipe.transform(`[click](${href})`)
      expect(html).not.toContain('<a')
      expect(html).toContain('click')
    }
  })

  it('should show the actual hostname beside web links with misleading labels', () => {
    for (const protocol of ['http', 'https']) {
      const html = pipe.transform(
        `[docs.paperless-ngx.com](${protocol}://docs.paperless-ngx.com@otherdomain.example/path?secret=1)`
      )
      expect(html).toContain(
        '</a> <span class="text-muted small">(otherdomain.example)</span>'
      )
      expect(html).not.toContain('(docs.paperless-ngx.com)')
    }
  })

  it('should omit the hostname label for mailto links', () => {
    expect(pipe.transform('[mail](mailto:a@b.c)')).toBe(
      '<p><a target="_blank" rel="noopener noreferrer nofollow" href="mailto:a@b.c">mail</a></p>\n'
    )
  })

  it('should escape link titles', () => {
    const html = pipe.transform(
      '[x](https://a.example "a\\" onmouseover=\\"1")'
    )
    expect(html).not.toMatch(/"\s*onmouseover=/)
  })
})
