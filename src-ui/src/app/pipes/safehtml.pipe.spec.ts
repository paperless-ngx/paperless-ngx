import { TestBed } from '@angular/core/testing'
import { BrowserModule, DomSanitizer } from '@angular/platform-browser'
import { SafeHtmlPipe } from './safehtml.pipe'

describe('SafeHtmlPipe', () => {
  let pipe: SafeHtmlPipe

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SafeHtmlPipe],
      imports: [BrowserModule],
    })
    pipe = TestBed.inject(SafeHtmlPipe)
  })

  it('should bypass security and trust the url', () => {
    const html = '<div>some content</div>'
    const domSanitizer = TestBed.inject(DomSanitizer)
    const sanitizerSpy = jest.spyOn(domSanitizer, 'bypassSecurityTrustHtml')
    let safeHtml = pipe.transform(html)
    expect(safeHtml).not.toBeNull()
    expect(sanitizerSpy).toHaveBeenCalled()
  })
})
