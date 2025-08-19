export function getFilenameFromContentDisposition(header: string): string {
  if (!header) {
    return null
  }

  // Try filename* (RFC 5987)
  const filenameStar = header.match(/filename\*=(?:UTF-\d['']*)?([^;]+)/i)
  if (filenameStar?.[1]) {
    try {
      return decodeURIComponent(filenameStar[1])
    } catch (e) {
      // Ignore decoding errors and fall through
    }
  }

  // Fallback to filename=
  const filenameMatch = header.match(/filename="?([^"]+)"?/)
  if (filenameMatch?.[1]) {
    return filenameMatch[1]
  }

  return null
}
