import { TestBed } from '@angular/core/testing'
import { SafeUrlPipe } from './safeurl.pipe'
import { BrowserModule, DomSanitizer } from '@angular/platform-browser'

describe('SafeUrlPipe', () => {
  let pipe: SafeUrlPipe

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SafeUrlPipe],
      imports: [BrowserModule],
    })
    pipe = TestBed.inject(SafeUrlPipe)
  })

  it('should bypass security and trust the url', () => {
    const url = 'https://example.com'
    const domSanitizer = TestBed.inject(DomSanitizer)
    const sanitizerSpy = jest.spyOn(
      domSanitizer,
      'bypassSecurityTrustResourceUrl'
    )

    let safeResourceUrl = pipe.transform(url)
    expect(safeResourceUrl).not.toBeNull()
    expect(sanitizerSpy).toHaveBeenCalled()

    safeResourceUrl = pipe.transform(null)
    expect(safeResourceUrl).not.toBeNull()
    expect(sanitizerSpy).toHaveBeenCalled()
  })
})
