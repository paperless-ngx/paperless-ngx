import {
  BRIGHTNESS,
  computeLuminance,
  estimateBrightnessForColor,
  hexToHsl,
  randomColor,
  rgbToHsl,
} from './color'

describe('Color Utils', () => {
  it('should convert hex to hsl', () => {
    let hsl = hexToHsl('#0000FF')
    expect(hsl).toEqual({
      h: 0.6666666666666666,
      s: 1,
      l: 0.5,
    })
  })

  it('should compute luminance', () => {
    let luminance = computeLuminance({ r: 0, g: 0, b: 0 })
    expect(luminance).toEqual(0)
    luminance = computeLuminance({ r: 255, g: 255, b: 255 })
    expect(luminance).toEqual(1)
    luminance = computeLuminance({ r: 128, g: 128, b: 128 })
    expect(luminance).toBeCloseTo(0.22)
  })

  it('should estimate brightness', () => {
    let brightness = estimateBrightnessForColor('#FFFF00') // yellow
    expect(brightness).toEqual(BRIGHTNESS.LIGHT)
    brightness = estimateBrightnessForColor('#800000') // maroon
    expect(brightness).toEqual(BRIGHTNESS.DARK)
  })

  it('should convert rgb to hsl', () => {
    let hsl = rgbToHsl(0, 255, 0)
    expect(hsl).toEqual([0.3333333333333333, 1, 0.5])
    hsl = rgbToHsl(255, 255, 0)
    expect(hsl).toEqual([0.16666666666666666, 1, 0.5])
    hsl = rgbToHsl(0, 0, 255)
    expect(hsl).toEqual([0.6666666666666666, 1, 0.5])
    hsl = rgbToHsl(128, 128, 128)
    expect(hsl).toEqual([0, 0, 0.5019607843137255])
  })

  it('should return a random color', () => {
    expect(randomColor()).not.toBeNull()
  })
})
