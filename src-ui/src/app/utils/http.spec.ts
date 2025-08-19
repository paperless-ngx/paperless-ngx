import { getFilenameFromContentDisposition } from './http'

describe('getFilenameFromContentDisposition', () => {
  it('should extract filename from Content-Disposition header with filename*', () => {
    const header = "attachment; filename*=UTF-8''example%20file.txt"
    expect(getFilenameFromContentDisposition(header)).toBe('example file.txt')
  })

  it('should extract filename from Content-Disposition header with filename=', () => {
    const header = 'attachment; filename="example-file.txt"'
    expect(getFilenameFromContentDisposition(header)).toBe('example-file.txt')
  })

  it('should prioritize filename* over filename if both are present', () => {
    const header =
      'attachment; filename="fallback.txt"; filename*=UTF-8\'\'preferred%20file.txt'
    const result = getFilenameFromContentDisposition(header)
    expect(result).toBe('preferred file.txt')
  })

  it('should gracefully fall back to null', () => {
    // invalid UTF-8 sequence
    expect(
      getFilenameFromContentDisposition("attachment; filename*=UTF-8''%E0%A4%A")
    ).toBeNull()
    // missing filename
    expect(getFilenameFromContentDisposition('attachment;')).toBeNull()
    // empty header
    expect(getFilenameFromContentDisposition(null)).toBeNull()
  })
})
