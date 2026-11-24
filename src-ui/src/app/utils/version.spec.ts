import { compareVersions } from './version'

describe('compareVersions', () => {
  it('should compare versions numerically', () => {
    expect(compareVersions('3.5.1', '3.5.0')).toBeGreaterThan(0)
    expect(compareVersions('3.10.0', '3.9.9')).toBeGreaterThan(0)
    expect(compareVersions('3.4.2', '3.5.0')).toBeLessThan(0)
    expect(compareVersions('3.5.0', '3.5.0')).toEqual(0)
    expect(compareVersions('3.5', '3.5.0')).toEqual(0)
  })
})
