/**
 * DFlip Utility Functions
 */

import { DEFAULTS, DIRECTION } from './constants.js'

export const isMouseEnabled = 'onmousedown' in window

export const userAgent = navigator.userAgent

export const drag = {
  left: 0,
  right: 1,
  none: -1,
}

export const mouseEvents = isMouseEnabled
  ? { type: 'mouse', start: 'mousedown', move: 'mousemove', end: 'mouseup' }
  : { type: 'touch', start: 'touchstart', move: 'touchmove', end: 'touchend' }

export const html = {
  div: '<div/>',
  img: '<img/>',
  a: '<a>',
  input: "<input type='text'/>",
}

export const isset = (e, t) => (e == null ? t : e)
export const toDeg = (e) => (e * 180) / Math.PI
export const transition = (e, t) => (e ? t / 1e3 + 's ease-out' : '0s none')

export const httpsCorrection = (e) => {
  const t = window.location
  if (t.href.indexOf('https://') > -1 && e.indexOf(t.hostname) > -1) {
    e = e.replace('http://', 'https://')
  }
  if (t.href.indexOf('http://') > -1 && e.indexOf(t.hostname) > -1) {
    e = e.replace('https://', 'http://')
  }
  return e
}

export const bg = (e) => '#fff' + bgImage(e)
export const bgImage = (e) => (e == null || e == 'blank' ? '' : ` url(${e})`)
export const src = (e) => (e != null ? '' + e + '' : '')
export const limitAt = (e, t, i) => (e < t ? t : e > i ? i : e)
export const distOrigin = (e, t) => Math.sqrt(Math.pow(e, 2) + Math.pow(t, 2))
export const distPoints = (e, t, i, n) =>
  Math.sqrt(Math.pow(i - e, 2) + Math.pow(n - t, 2))

export const calculateScale = (e, t) => {
  const i = distPoints(e[0].x, e[0].y, e[1].x, e[1].y)
  const n = distPoints(t[0].x, t[0].y, t[1].x, t[1].y)
  return n / i
}

export const getVectorAvg = (e) => ({
  x: e.map((e) => e.x).reduce((a, b) => a + b, 0) / e.length,
  y: e.map((e) => e.y).reduce((a, b) => a + b, 0) / e.length,
})

export const getTouches = (e, t = { left: 0, top: 0 }) => {
  return Array.prototype.slice.call(e.touches).map((e) => ({
    x: e.pageX - t.left,
    y: e.pageY - t.top,
  }))
}

export const angleByDistance = (e, t) => {
  const i = t / 2
  const n = limitAt(e, 0, t)
  return n < i ? toDeg(Math.asin(n / i)) : 90 + toDeg(Math.asin((n - i) / i))
}

export const log = (e) => {
  if (DEFAULTS.enableDebugLog == true && window.console) console.log(e)
}

export const nearestPowerOfTwo = (e, t = 2048) =>
  Math.min(t, Math.pow(2, Math.ceil(Math.log(e) / Math.LN2)))

export const getFullscreenElement = () =>
  document.fullscreenElement ||
  document.mozFullScreenElement ||
  document.webkitFullscreenElement ||
  document.msFullscreenElement

export const hasFullscreenEnabled = () =>
  document.fullscreenEnabled ||
  document.mozFullScreenEnabled ||
  document.webkitFullScreenEnabled ||
  document.msFullscreenEnabled

export const getBasePage = (e) => Math.floor(e / 2) * 2

export const prefix = (() => {
  const e = window.getComputedStyle(document.documentElement, ''),
    t = Array.prototype.slice
      .call(e)
      .join('')
      .match(/-(moz|webkit|ms)-/)[1],
    i = 'WebKit|Moz|MS'.match(new RegExp('(' + t + ')', 'i'))[1]
  return {
    dom: i,
    lowercase: t,
    css: '-' + t + '-',
    js: t[0].toUpperCase() + t.substr(1),
  }
})()

const scriptCallbacks = {}
export const getScript = (e, t, n) => {
  let a = scriptCallbacks[e]
  let o
  function r(e, t) {
    if (o != null) {
      if (t || !o.readyState || /loaded|complete/.test(o.readyState)) {
        o.onload = o.onreadystatechange = null
        o = null
        if (!t) {
          for (let i = 0; i < a.length; i++) {
            if (a[i]) a[i]()
            a[i] = null
          }
          n = null
        }
      }
    }
  }
  if (jQuery(`script[src='${e}']`).length === 0) {
    a = scriptCallbacks[e] = []
    a.push(t)
    o = document.createElement('script')
    const s = document.body.getElementsByTagName('script')[0]
    o.async = true
    o.setAttribute('data-cfasync', false)
    if (s != null) {
      s.parentNode.insertBefore(o, s)
    } else {
      document.body.appendChild(o)
    }
    o.addEventListener('load', r, false)
    o.addEventListener('readystatechange', r, false)
    o.addEventListener('complete', r, false)
    if (n) {
      o.addEventListener('error', n, false)
    }
    o.src = e + (prefix.dom == 'MS' ? '?' + Math.random() : '')
  } else {
    a.push(t)
  }
}

export const isHardPage = (e, t, i, n) => {
  if (e != null) {
    if (e == 'cover') {
      return (
        t == 0 || (n && t == 1) || t == Math.ceil(i / (n ? 1 : 2)) - (n ? 0 : 1)
      )
    } else if (e == 'all') {
      return true
    } else {
      const a = (',' + e + ',').indexOf(',' + (t * 2 + 1) + ',') > -1
      const o = (',' + e + ',').indexOf(',' + (t * 2 + 2) + ',') > -1
      return a || o
    }
  }
  return false
}

export const fixMouseEvent = (e) => {
  if (e) {
    const t = e.originalEvent || e
    if (t.changedTouches && t.changedTouches.length > 0) {
      const n = jQuery.event.fix(e)
      const a = t.changedTouches[0]
      n.clientX = a.clientX
      n.clientY = a.clientY
      n.pageX = a.pageX
      n.touches = t.touches
      n.pageY = a.pageY
      n.movementX = a.movementX
      n.movementY = a.movementY
      return n
    }
  }
  return e
}

export const hasWebgl = (() => {
  try {
    const e = document.createElement('canvas')
    return !!(
      window.WebGLRenderingContext &&
      (e.getContext('webgl') || e.getContext('experimental-webgl'))
    )
  } catch (e) {
    return false
  }
})()

export const isBookletMode = (e) =>
  e.pageMode == DEFAULTS.pageMode && e.singlePageMode == DEFAULTS.singlePageMode

export const isRTLMode = (e) => e.direction == DIRECTION.RTL

export const isMobile = (() => {
  let e = false
  ;((t) => {
    if (
      /(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\.(browser|link)|vodafone|wap|windows ce|xda|xiino|android|ipad|playbook|silk/i.test(
        t
      ) ||
      /1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\-|your|zeto|zte\-/i.test(
        t.substr(0, 4)
      )
    )
      e = true
  })(userAgent || navigator.vendor || window.opera)
  return e
})()

export const createBlob = (data, type) => {
  if (typeof Blob !== 'undefined') {
    return new Blob([data], { type: type })
  }
  // Fallback for older browsers if necessary, though modern dflip targets modern browsers
  const BlobBuilder =
    window.BlobBuilder ||
    window.WebKitBlobBuilder ||
    window.MozBlobBuilder ||
    window.MSBlobBuilder
  if (BlobBuilder) {
    const bb = new BlobBuilder()
    bb.append(data)
    return bb.getBlob(type)
  }
  return null
}

export const createObjectURL = (data, type) => {
  const alphabet =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
  if (typeof URL !== 'undefined' && URL.createObjectURL) {
    const blob = createBlob(data, type)
    return URL.createObjectURL(blob)
  }
  // Base64 fallback
  let res = 'data:' + type + ';base64,'
  for (let i = 0, len = data.length; i < len; i += 3) {
    const l = data[i] & 255
    const c = data[i + 1] & 255
    const u = data[i + 2] & 255
    const d = l >> 2,
      f = ((l & 3) << 4) | (c >> 4)
    const h = i + 1 < len ? ((c & 15) << 2) | (u >> 6) : 64
    const p = i + 2 < len ? u & 63 : 64
    res += alphabet[d] + alphabet[f] + alphabet[h] + alphabet[p]
  }
  return res
}
