import { matchesSearchText } from './text-search'

describe('text search utilities', () => {
  it('matches text accent-insensitively', () => {
    expect(matchesSearchText('R\u00e9sum\u00e9', 'resume')).toBeTruthy()
    expect(matchesSearchText('S\u00f8ren', 'soren')).toBeTruthy()
    expect(matchesSearchText('\u0152uvre', 'oeuvre')).toBeTruthy()
    expect(matchesSearchText('Invoice', 'receipt')).toBeFalsy()
  })

  it('matches all whitespace-separated search terms independently', () => {
    expect(matchesSearchText('taxes 2026', 'tax 26')).toBeTruthy()
    expect(matchesSearchText('2026 taxes', 'tax 26')).toBeTruthy()
    expect(matchesSearchText('Tax\u00e9s 2026', 'taxe 26')).toBeTruthy()
    expect(matchesSearchText('taxes 2026', 'tax receipt')).toBeFalsy()
  })

  it('matches a large set of tag names without blocking input', () => {
    const tagNames = Array.from(
      { length: 1280 },
      (_, index) =>
        `Customer Party ${index} Jos\u00e9 M\u00fcller \u00c5ngstr\u00f6m`
    )

    const start = performance.now()
    const matches = tagNames.filter((name) => matchesSearchText(name, 'party'))
    const duration = performance.now() - start

    expect(matches).toHaveLength(tagNames.length)
    // The previous implementation took roughly 500 ms for this workload.
    expect(duration).toBeLessThan(250)
  })
})
