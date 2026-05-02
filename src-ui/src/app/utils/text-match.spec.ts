import { textMatchesTokens } from './text-match'

describe('textMatchesTokens', () => {
  it('returns true for empty / whitespace-only queries', () => {
    expect(textMatchesTokens('Hello', '')).toBe(true)
    expect(textMatchesTokens('Hello', null)).toBe(true)
    expect(textMatchesTokens('Hello', undefined)).toBe(true)
    expect(textMatchesTokens('Hello', '   ')).toBe(true)
  })

  it('returns false when haystack is missing but tokens exist', () => {
    expect(textMatchesTokens(null, 'foo')).toBe(false)
    expect(textMatchesTokens(undefined, 'foo')).toBe(false)
  })

  it('matches a single substring case-insensitively', () => {
    expect(textMatchesTokens('Lorem Ipsum Dolor 2025', 'lor')).toBe(true)
    expect(textMatchesTokens('Lorem Ipsum Dolor 2025', 'xyz')).toBe(false)
  })

  it('matches when all whitespace-separated tokens are present in any order', () => {
    expect(textMatchesTokens('Lorem Ipsum Dolor 2025', 'Lor 2025')).toBe(true)
    expect(textMatchesTokens('Lorem Ipsum Dolor 2025', '2025 Lor')).toBe(true)
    expect(textMatchesTokens('Lorem Ipsum Dolor 2025', 'Lor Ipsum 2025')).toBe(
      true
    )
  })

  it('fails when any token is missing', () => {
    expect(textMatchesTokens('Lorem Ipsum Dolor 2025', 'Lor 2024')).toBe(false)
  })

  it('collapses multiple whitespace between tokens', () => {
    expect(textMatchesTokens('Lorem Ipsum Dolor 2025', 'Lor\t\n  2025')).toBe(
      true
    )
  })
})
