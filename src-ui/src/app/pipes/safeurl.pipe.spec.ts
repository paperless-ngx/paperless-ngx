import { TestBed } from '@angular/core/testing'
import { BrowserModule, DomSanitizer } from '@angular/platform-browser'
import { SafeUrlPipe } from './safeurl.pipe'

describe('SafeUrlPipe', () => {
  let pipe: SafeUrlPipe

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SafeUrlPipe],
      imports: [BrowserModule],
    })
    pipe = TestBed.inject(SafeUrlPipe)
  })

  it('should trust only same-origin http/https urls', () => {
    const origin = window.location.origin
    const url = `${origin}/some/path`
    const domSanitizer = TestBed.inject(DomSanitizer)
    const sanitizerSpy = jest.spyOn(
      domSanitizer,
      'bypassSecurityTrustResourceUrl'
    )

    const safeResourceUrl = pipe.transform(url)
    expect(safeResourceUrl).not.toBeNull()
    expect(sanitizerSpy).toHaveBeenCalledWith(url)
  })

  it('should return null for null or unsafe urls', () => {
    const sanitizerSpy = jest.spyOn(
      TestBed.inject(DomSanitizer),
      'bypassSecurityTrustResourceUrl'
    )

    expect(pipe.transform(null)).toBeTruthy()
    expect(sanitizerSpy).toHaveBeenCalledWith('')
    expect(pipe.transform('javascript:alert(1)')).toBeTruthy()
    expect(sanitizerSpy).toHaveBeenCalledWith('')
    const otherOrigin =
      window.location.origin === 'https://example.com'
        ? 'https://evil.com'
        : 'https://example.com'
    expect(pipe.transform(`${otherOrigin}/file`)).toBeTruthy()
    expect(sanitizerSpy).toHaveBeenCalledWith('')
  })

  it('should return null for malformed urls', () => {
    const sanitizerSpy = jest.spyOn(
      TestBed.inject(DomSanitizer),
      'bypassSecurityTrustResourceUrl'
    )

    expect(pipe.transform('http://[invalid-url')).toBeTruthy()
    expect(sanitizerSpy).toHaveBeenCalledWith('')
  })
})
