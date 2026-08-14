/**
 * DFlip Entry Point
 */

import * as CONSTANTS from './constants.js'
import * as UTILS from './utils.js'
import { FlipBook } from './factory.js'

// Setup Global DFLIP object for backward compatibility
const DFLIP = window.DFLIP || {}

Object.assign(DFLIP, CONSTANTS)
DFLIP.utils = UTILS
DFLIP.FlipBook = FlipBook

// Adapter for original DFLIP.defaults.extendOptions usage
DFLIP.defaults = CONSTANTS.DEFAULTS
DFLIP.defaults.extendOptions = (target, options) =>
  jQuery.extend(true, {}, target, options)

// jQuery Plugin Registration
;(function ($) {
  if ($.fn) {
    $.fn.flipBook = function (source, options) {
      const mergedOptions = $.extend(true, {}, DFLIP.defaults, options)
      return new FlipBook(this, source, mergedOptions)
    }
  }
})(jQuery)

// Global Setup on evaluation
;(function ($) {
  $(document).ready(function () {
    if (typeof window.dFlipLocation === 'undefined') {
      try {
        const url = import.meta.url
        if (url) {
          const parts = url.split('/')
          window.dFlipLocation = parts.slice(0, -4).join('/') + '/'
        }
      } catch (e) {
        $('script').each(function () {
          const src = $(this).attr('src') || ''
          if (src.indexOf('dflip') > -1 && src.indexOf('js/') > -1) {
            const parts = src.split('/')
            if (src.indexOf('dflip') > -1) {
              window.dFlipLocation = parts.slice(0, -4).join('/') + '/'
            } else {
              window.dFlipLocation = parts.slice(0, -2).join('/') + '/'
            }
            return false
          }
        })
      }
    }

    if (typeof window.dFlipLocation !== 'undefined') {
      let loc = window.dFlipLocation
      if (loc.length > 2 && loc.slice(-1) !== '/') {
        loc += '/'
        window.dFlipLocation = loc
      }
      DFLIP.defaults.pdfjsSrc = loc + 'js/libs/pdf.min.js'
      DFLIP.defaults.pdfjsWorkerSrc = loc + 'js/libs/pdf.worker.min.js'
      DFLIP.defaults.imageResourcesPath = loc + 'images/pdfjs/'
      DFLIP.defaults.cMapUrl = loc + 'js/libs/cmaps/'
    }
  })
})(jQuery)

window.DFLIP = DFLIP
export default DFLIP
