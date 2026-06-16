/**
 * Returns a canonical, accent‑free lowercase form of the string,
 * using Unicode NFD decomposition to strip combining diacritical marks.
 */
export function normalizeString(str: string): string {
  return str
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}
