// see https://github.com/dateutil/dateutil/issues/878 , JS Date does not
// seem to accept these strings as valid dates so we must normalize offset
export function normalizeDateStr(dateStr: string): string {
  return dateStr.replace(/-(\d\d):\d\d:\d\d/gm, `-$1:00`)
}
