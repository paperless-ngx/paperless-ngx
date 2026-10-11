import { SecurityContext } from '@angular/core'
import { TestBed } from '@angular/core/testing'
import { DomSanitizer } from '@angular/platform-browser'
import { ChatMarkdownPipe } from './chat-markdown.pipe'

describe('ChatMarkdownPipe', () => {
  let pipe: ChatMarkdownPipe
  let sanitizer: DomSanitizer

  beforeEach(() => {
    TestBed.configureTestingModule({})
    pipe = TestBed.runInInjectionContext(() => new ChatMarkdownPipe())
    sanitizer = TestBed.inject(DomSanitizer)
  })

  it('renders common Markdown and nested task lists', () => {
    const html = render(
      '# Heading\n\n**Bold** and *italic* and ***both*** and ~~deleted~~ and <u>underlined</u>.\n\n- [x] Done\n  - Nested\n- [ ] Open\n\n1. First\n2. Second'
    )

    expect(html).toContain('<h1>Heading</h1>')
    expect(html).toContain('<strong>Bold</strong>')
    expect(html).toContain('<em>italic</em>')
    expect(html).toContain('<strong><em>both</em></strong>')
    expect(html).toContain('<del>deleted</del>')
    expect(html).toContain('<u>underlined</u>')
    expect(html).toContain('class="chat-task-checkbox checked"')
    expect(html).toContain('class="chat-task-checkbox"')
    expect(html).toContain('<ol>')
  })

  it('renders tables, highlighted code, and TeX math', () => {
    const html = render(
      '| Name | Amount |\n| :--- | ---: |\n| Revenue | 125 |\n\n```python\ndef hello():\n    return "Hello"\n```\n\n\\(E=mc^2\\)\n\n\\[\\frac{a}{b}\\]'
    )

    expect(html).toContain('<table>')
    expect(html).toContain('align="left"')
    expect(html).toContain('align="right"')
    expect(html).toContain('class="hljs language-python"')
    expect(html).toContain('hljs-keyword')
    expect(html).toContain('class="katex"')
    expect(html).toContain('katex-display')
  })

  it('sanitizes unsafe HTML while retaining safe formatting', () => {
    const html = render('<u>Safe</u><script>alert(1)</script>')
    expect(html).toContain('<u>Safe</u>')
    expect(html).not.toContain('<script>')
  })

  function render(value: string): string {
    return sanitizer.sanitize(SecurityContext.HTML, pipe.transform(value)) ?? ''
  }
})
