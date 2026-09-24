import { environment } from 'src/environments/environment'
import { getShareUrl } from './share-link'

describe('getShareUrl', () => {
  const originalApiBaseUrl = environment.apiBaseUrl

  afterEach(() => {
    environment.apiBaseUrl = originalApiBaseUrl
  })

  it('should derive the URL from the API base URL by default', () => {
    environment.apiBaseUrl = 'http://example.com:1234/subpath/api/'
    expect(getShareUrl('abc')).toEqual(
      'http://example.com:1234/subpath/share/abc'
    )
    expect(getShareUrl('abc', null)).toEqual(
      'http://example.com:1234/subpath/share/abc'
    )
  })

  it('should use the configured base URL if set', () => {
    environment.apiBaseUrl = 'http://example.com/api/'
    expect(getShareUrl('abc', 'https://share.example.org')).toEqual(
      'https://share.example.org/share/abc'
    )
    expect(getShareUrl('abc', 'https://share.example.org/paperless/')).toEqual(
      'https://share.example.org/paperless/share/abc'
    )
  })
})
