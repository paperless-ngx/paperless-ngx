export function textMatchesTokens(haystack: string, query: string): boolean {
  if (!query) return true
  const tokens = query.split(/\s+/).filter((t) => t.length > 0)
  if (tokens.length === 0) return true
  if (haystack == null) return false
  const lowered = haystack.toLowerCase()
  return tokens.every((token) => lowered.includes(token.toLowerCase()))
}
