import { HSL, RGB } from 'ngx-color'

export const BRIGHTNESS = {
  LIGHT: 'light',
  DARK: 'dark',
}

export function componentToHex(c) {
  var hex = Math.floor(c).toString(16)
  return hex.length == 1 ? '0' + hex : hex
}

/**
 *
 * https://axonflux.com/handy-rgb-to-hsl-and-rgb-to-hsv-color-model-c
 * Converts an HSL color value to RGB. Conversion formula
 * adapted from http://en.wikipedia.org/wiki/HSL_color_space.
 * Assumes h, s, and l are contained in the set [0, 1] and
 * returns r, g, and b in the set [0, 255].
 *
 * @param   Number  h       The hue
 * @param   Number  s       The saturation
 * @param   Number  l       The lightness
 * @return  Array           The RGB representation
 */

function hue2rgb(p, q, t) {
  if (t < 0) t += 1
  if (t > 1) t -= 1
  if (t < 1 / 6) return p + (q - p) * 6 * t
  if (t < 1 / 2) return q
  if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6
  return p
}

export function hslToRgb(h, s, l) {
  var r, g, b

  if (s == 0) {
    r = g = b = l // achromatic
  } else {
    var q = l < 0.5 ? l * (1 + s) : l + s - l * s
    var p = 2 * l - q
    r = hue2rgb(p, q, h + 1 / 3)
    g = hue2rgb(p, q, h)
    b = hue2rgb(p, q, h - 1 / 3)
  }

  return [r * 255, g * 255, b * 255]
}

/**
 * https://axonflux.com/handy-rgb-to-hsl-and-rgb-to-hsv-color-model-c
 * Converts an RGB color value to HSL. Conversion formula
 * adapted from http://en.wikipedia.org/wiki/HSL_color_space.
 * Assumes r, g, and b are contained in the set [0, 255] and
 * returns h, s, and l in the set [0, 1].
 *
 * @param   Number  r       The red color value
 * @param   Number  g       The green color value
 * @param   Number  b       The blue color value
 * @return  Array           The HSL representation
 */
export function rgbToHsl(r, g, b) {
  ;(r /= 255), (g /= 255), (b /= 255)
  var max = Math.max(r, g, b),
    min = Math.min(r, g, b)
  var h,
    s,
    l = (max + min) / 2

  if (max == min) {
    h = s = 0 // achromatic
  } else {
    var d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0)
        break
      case g:
        h = (b - r) / d + 2
        break
      case b:
        h = (r - g) / d + 4
        break
    }
    h /= 6
  }

  return [h, s, l]
}

export function hexToHsl(hex: string): HSL {
  const rgb = hexToRGB(hex)
  const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b)
  return { h: hsl[0], s: hsl[1], l: hsl[2] }
}

export function hexToRGB(hex: string): RGB {
  hex = hex.replace('#', '')
  let aRgbHex = hex.match(/.{1,2}/g)
  return {
    r: parseInt(aRgbHex[0], 16),
    g: parseInt(aRgbHex[1], 16),
    b: parseInt(aRgbHex[2], 16),
  }
}

export function computeLuminance(color: RGB) {
  // Formula: http://www.w3.org/TR/2008/REC-WCAG20-20081211/#relativeluminancedef
  const colorKeys = Object.keys(color)
  for (var i = 0; i < 3; i++) {
    var rgb = color[colorKeys[i]]
    rgb /= 255
    rgb = rgb < 0.03928 ? rgb / 12.92 : Math.pow((rgb + 0.055) / 1.055, 2.4)
    color[i] = rgb
  }
  return 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
}

export function estimateBrightnessForColor(colorHex: string) {
  // See <https://www.w3.org/TR/WCAG20/#contrast-ratiodef>
  // Adapted from https://api.flutter.dev/flutter/material/ThemeData/estimateBrightnessForColor.html
  const rgb = hexToRGB(colorHex)
  const luminance = computeLuminance(rgb)
  const kThreshold = 0.15
  return (luminance + 0.05) * (luminance + 0.05) > kThreshold
    ? BRIGHTNESS.LIGHT
    : BRIGHTNESS.DARK
}

export function randomColor() {
  let rgb = hslToRgb(Math.random(), 0.6, Math.random() * 0.4 + 0.4)
  return `#${componentToHex(rgb[0])}${componentToHex(rgb[1])}${componentToHex(
    rgb[2]
  )}`
}
