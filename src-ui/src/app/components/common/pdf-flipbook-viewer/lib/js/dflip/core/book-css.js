/**
 * DFlip Book CSS Class
 */

import { DIRECTION, PAGE_MODE, SINGLE_PAGE_MODE } from '../constants.js'
import {
  isMobile,
  isBookletMode,
  isRTLMode,
  isHardPage,
  fixMouseEvent,
  getBasePage,
  limitAt,
  angleByDistance,
  log,
} from '../utils.js'
import { TWEEN } from '../tween.js'

export class BookCSS {
  constructor(options, container) {
    const self = this
    const $ = jQuery
    self.type = 'BookCSS'
    self.images = options.images || []
    self.pageCount = options.pageCount || 1
    self.foldSense = 50
    self.stackCount = 4
    self.mode = 'css'
    self.pages = []
    self.duration = options.duration
    self.container = $(container)
    self.options = options
    self.drag = -1 // d.none
    self.pageMode =
      options.pageMode ||
      (isMobile || self.pageCount <= 2 ? PAGE_MODE.SINGLE : PAGE_MODE.DOUBLE)
    self.singlePageMode =
      options.singlePageMode ||
      (isMobile ? SINGLE_PAGE_MODE.BOOKLET : SINGLE_PAGE_MODE.ZOOM)
    self.swipe_threshold = isMobile ? 15 : 50
    self.direction = options.direction || DIRECTION.LTR
    self.startPage = 1
    self.endPage = self.pageCount
    self._activePage = options.openPage || self.startPage
    self.hardConfig = options.hard

    self.animateF = () => {
      if (typeof TWEEN !== 'undefined' && TWEEN.getAll().length > 0)
        TWEEN.update()
      else clearInterval(self.animate)
    }

    self.init(options)
    self.skipDrag = false

    const setDragPage = (point) => {
      if (self.dragPage != point.page && point.page.visible == true) {
        if (self.dragPage && self.dragPage.clearTween)
          self.dragPage.clearTween(true)
        self.dragPage = point.page
        self.corner = point.corner
        self.dragPage.pendingPoint = point
      }
    }

    self.onMouseMove = (e) => {
      const point = self.eventToPoint(e)
      if (
        e.touches != null &&
        e.touches.length == 2 &&
        self.startTouches != null
      ) {
        self.zoomDirty = true
        const scale = 1 // calculate scale from touches
        self.stage.css({
          transform: `translate3d(${self.left}px,${self.top}px,0) scale3d(${scale},${scale},1)`,
        })
        e.preventDefault()
      }
      if (
        (e.touches != null && e.touches.length > 1) ||
        self.startPoint == null ||
        self.startTouches != null
      )
        return

      const page = self.dragPage || point.page
      if (self.contentProvider.zoomScale !== 1) {
        if (e.touches != null || self.isPanning == true) {
          self.pan(point)
          e.preventDefault()
        }
      } else {
        if (self.skipDrag !== true) {
          if (!self.isFlipping()) {
            if (self.dragPage != null || point.isInside == true) {
              const corner = self.corner || point.corner
              if (page.isHard) {
                const isRight = corner == 'br' || corner == 'tr'
                const angle = angleByDistance(point.distance, point.fullWidth)
                page.updateAngle(angle * (isRight ? -1 : 1), isRight)
              } else {
                page.updatePoint(point, self)
              }
              page.magnetic = true
              page.magneticCorner = point.corner
              e.preventDefault()
            }
          }
        }
      }
    }

    // More event handlers would go here...
    // Simplified for now, similar to original code structure but modularized.
  }

  isFlipping() {
    for (let i = 0; i < this.pages.length; i++) {
      if (this.pages[i].isFlipping) return true
    }
    return false
  }

  init(options) {
    const $ = jQuery
    this.stage = $("<div class='df-book-stage'>")
    this.wrapper = $("<div class='df-book-wrapper'>")
    this.shadow = $("<div class='df-book-shadow'>")
    this.container.append(this.stage)
    this.stage.append(this.wrapper)
    this.wrapper.append(this.shadow)
    this.createStack(options)
  }

  createStack(options) {
    // Similar to Book.js createStack but for CSS pages
  }

  // Implementation of eventToPoint, pan, gotoPage, updatePage, etc.
}
