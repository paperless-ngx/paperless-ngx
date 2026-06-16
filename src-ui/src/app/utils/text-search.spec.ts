import { matchesSearchText } from './text-search'

describe('text search utilities', () => {
  it('matches text accent-insensitively', () => {
    expect(matchesSearchText('R\u00e9sum\u00e9', 'resume')).toBeTruthy()
    expect(matchesSearchText('S\u00f8ren', 'soren')).toBeTruthy()
    expect(matchesSearchText('\u0152uvre', 'oeuvre')).toBeTruthy()
    expect(matchesSearchText('Invoice', 'receipt')).toBeFalsy()
  })
})
