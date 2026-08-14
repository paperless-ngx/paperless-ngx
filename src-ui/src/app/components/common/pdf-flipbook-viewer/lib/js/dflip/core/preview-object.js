/**
 * DFlip Preview Object Class
 */

import {
  DIRECTION,
  PAGE_MODE,
  CONTROLSPOSITION,
  SOURCE_TYPE,
  SINGLE_PAGE_MODE,
  VERSION,
} from '../constants.js'
import {
  log,
  limitAt,
  getBasePage,
  hasFullscreenEnabled,
  isRTLMode,
  distOrigin,
} from '../utils.js'
import { TWEEN } from '../tween.js'

export class PreviewObject {
  constructor(options) {
    options = options || {}
    this.type = 'PreviewObject'
    const self = this
    self.zoomValue = 1
    self.options = options

    const onResize = () => {
      setTimeout(() => {
        self.resize()
      }, 50)
    }

    window.addEventListener('resize', onResize, false)

    this.dispose = () => {
      if (this.target && this.target.children) {
        for (let i = 0; i < this.target.children.length; i++) {
          const child = this.target.children[i]
          if (child && child.currentTween) child.currentTween.stop()
        }
      }
      if (this.zoomTween) {
        if (this.zoomTween.stop) this.zoomTween.stop()
        this.zoomTween = null
      }
      if (this.container && this.container.info && this.container.info.remove)
        this.container.info.remove()
      if (this.target && this.target.dispose) this.target.dispose()
      this.target = null
      if (this.stage && this.stage.dispose) this.stage.dispose()
      this.stage = null
      if (this.ui && this.ui.dispose) this.ui.dispose()
      this.ui = null
      if (this.contentProvider && this.contentProvider.dispose)
        this.contentProvider.dispose()
      this.contentProvider = null
      window.removeEventListener('resize', onResize)
    }
  }

  start() {
    this.target.gotoPage(this.target.startPage)
  }

  end() {
    this.target.gotoPage(this.target.endPage)
  }

  next() {}
  prev() {}

  calculateSize(
    stageHeight,
    containerWidth,
    windowHeight,
    paddingVertical,
    paddingHorizontal,
    isAutoHeight,
    ratio,
    isSinglePage
  ) {
    let height = stageHeight
    const availWidth = containerWidth - paddingHorizontal
    const availHeight = height - paddingVertical
    const widthPerSide = Math.ceil(isSinglePage ? availWidth : availWidth / 2)
    const calculatedHeight = widthPerSide / ratio
    let limitHeight = null

    if (isAutoHeight) {
      limitHeight = Math.min(calculatedHeight, windowHeight - paddingVertical)
      height = limitHeight
    } else {
      limitHeight = Math.min(availHeight, windowHeight - paddingVertical)
    }

    const isWide = calculatedHeight > limitHeight
    let finalHeight, finalWidth

    if (isWide) {
      finalHeight = limitHeight
      finalWidth = Math.floor(finalHeight * ratio)
    } else {
      finalWidth = widthPerSide
      finalHeight = Math.ceil(widthPerSide / ratio)
    }

    if (isAutoHeight) {
      height = Math.max(finalHeight + paddingVertical, 320)
    }
    return {
      stageHeight: height,
      isWide: isWide,
      height: finalHeight,
      width: finalWidth,
    }
  }

  zoom(delta) {
    this.pendingZoom = true
    this.zoomDelta = delta
    this.resize()
    if (this.ui) this.ui.update()
  }

  resize() {
    const self = this
    if (
      self.target == null ||
      self.target.ui == null ||
      self.contentProvider == null ||
      self.contentProvider.viewport == null ||
      self.target.stage == null
    )
      return

    if (
      this.ui &&
      this.ui.isFullscreen == true &&
      hasFullscreenEnabled() == true &&
      document.fullscreenElement == null
    ) {
      this.ui.switchFullscreen()
    }

    const target = self.target,
      container = self.container,
      options = self.options,
      stage = target.stage,
      cp = self.contentProvider,
      ratio = cp.pageRatio,
      isRTL = isRTLMode(target),
      is3D = target.mode !== 'css',
      isSinglePage = target.pageMode == PAGE_MODE.SINGLE

    const isAutoHeight =
      this.ui.isFullscreen == true ? false : options.height === 'auto'
    const sideMenuWidth = 0

    const containerWidth = container.width()
    if (containerWidth < 400) {
      container.addClass('df-xs')
    } else {
      container.removeClass('df-xs')
    }

    const controlsHeight = container.find('.df-ui-controls').height()
    let paddingTop =
      options.paddingTop +
      (options.controlsPosition == CONTROLSPOSITION.TOP ? controlsHeight : 0)
    let paddingBottom =
      options.paddingBottom +
      (options.controlsPosition == CONTROLSPOSITION.BOTTOM ? controlsHeight : 0)
    let paddingLeft = options.paddingLeft
    let paddingRight = options.paddingRight

    paddingTop = limitAt(paddingTop, 0, paddingTop)
    paddingBottom = limitAt(paddingBottom, 0, paddingBottom)
    paddingLeft = limitAt(paddingLeft, 0, paddingLeft)
    paddingRight = limitAt(paddingRight, 0, paddingRight)

    const paddingVertical = paddingTop + paddingBottom
    const paddingHorizontal = paddingLeft + paddingRight
    const availableWidth = containerWidth - sideMenuWidth

    container.height(options.height)
    const windowHeight = jQuery(window).height()
    const stageH = Math.min(container.height(), windowHeight)

    const size = self.calculateSize(
      stageH,
      availableWidth,
      windowHeight,
      paddingVertical,
      paddingHorizontal,
      isAutoHeight,
      ratio,
      isSinglePage
    )
    let finalStageHeight = size.stageHeight

    if (isAutoHeight) {
      finalStageHeight = self.calculateSize(
        stageH,
        availableWidth + sideMenuWidth,
        windowHeight,
        paddingVertical,
        paddingHorizontal,
        isAutoHeight,
        ratio,
        isSinglePage
      ).stageHeight
    }

    container.height(finalStageHeight)
    const contentAvailWidth = availableWidth - paddingHorizontal
    const contentAvailHeight = finalStageHeight - paddingVertical

    let pageWidth = Math.floor(
      isSinglePage ? contentAvailWidth : contentAvailWidth / 2
    )
    let pageHeight = Math.floor(pageWidth / ratio)
    const isWide = pageHeight > contentAvailHeight

    if (isWide) {
      pageHeight = contentAvailHeight
      pageWidth = pageHeight * ratio
    }

    const maxZoom = (cp.maxZoom = cp.zoomViewport.height / pageHeight)

    if (self.zoomValue == null) self.zoomValue = 1
    if (cp.zoomScale == null) cp.zoomScale = 1

    if (self.pendingZoom == true && self.zoomDelta != null) {
      self.zoomValue =
        self.zoomDelta > 0
          ? self.zoomValue * self.options.zoomRatio
          : self.zoomValue / self.options.zoomRatio
      self.zoomValue = limitAt(self.zoomValue, 1, maxZoom)
      cp.zoomScale =
        self.zoomValue == 1 ? 1 : limitAt(self.zoomValue, 1, maxZoom)
    }

    const zoomScale = cp.zoomScale
    cp.checkViewportSize(pageWidth, pageHeight, zoomScale)

    if (cp.contentSourceType == SOURCE_TYPE.PDF) {
      pageWidth = cp.imageViewport.width / zoomScale
      pageHeight = cp.imageViewport.height / zoomScale
    }

    if (zoomScale != 1) {
      target.container.addClass('df-zoom-enabled')
    }

    const zoomWidth = (target.zoomWidth = Math.floor(pageWidth * zoomScale))
    const zoomHeight = (target.zoomHeight = Math.floor(pageHeight * zoomScale))
    const wrapperWidth = zoomWidth * 2

    if (is3D) {
      const scaleK = zoomHeight / target.height
      const widthK = availableWidth / finalStageHeight
      const v1 = (zoomScale * (pageHeight + paddingVertical)) / scaleK
      const v2 =
        (zoomScale * (pageWidth * (isSinglePage ? 1 : 2) + paddingHorizontal)) /
        scaleK
      const vFinal = isWide ? v1 : v2 / widthK

      stage.resizeCanvas(availableWidth, finalStageHeight)
      const targetZ =
        1 /
          ((2 * Math.tan((Math.PI * stage.camera.fov * 0.5) / 180)) /
            (vFinal / zoomScale)) +
        2.2
      stage.camera.updateProjectionMatrix()
      stage.renderRequestPending = true

      const offsetCenterY =
        ((paddingTop - paddingBottom) * (target.height / pageHeight)) /
        zoomScale /
        2
      const isZoomedOut = zoomScale == 1

      const currentCenterX = this.centerEnd || 0

      if (stage.camera.position.z !== targetZ && self.pendingZoom == true) {
        if (self.zoomTween != null) self.zoomTween.stop()
        self.zoomTween = new TWEEN.Tween({
          campos: stage.camera.position.z,
          otx: stage.orbitControl.target.x,
          oty: stage.orbitControl.target.y,
          otz: stage.orbitControl.target.z,
        })
          .delay(0)
          .to({ campos: targetZ, otx: 0, oty: offsetCenterY, otz: 0 }, 100)
          .onUpdate(function () {
            stage.camera.position.z = this.campos
            if (isZoomedOut) {
              stage.camera.position.y = this.oty
              stage.orbitControl.target = new THREE.Vector3(
                this.otx,
                this.oty,
                this.otz
              )
            }
            stage.orbitControl.update()
          })
          .easing(TWEEN.Easing.Linear.None)
          .onComplete(() => {
            stage.camera.position.z = targetZ
            if (zoomScale == 1) {
              stage.camera.position.set(0, offsetCenterY, targetZ)
              stage.orbitControl.target = new THREE.Vector3(0, offsetCenterY, 0)
            }
            stage.orbitControl.update()
          })
          .start()
      } else {
        if (zoomScale == 1) {
          stage.camera.position.set(0, offsetCenterY, targetZ)
          stage.orbitControl.target = new THREE.Vector3(0, offsetCenterY, 0)
        }
        stage.orbitControl.update()
      }
      stage.orbitControl.update()
      stage.orbitControl.mouseButtons.ORBIT =
        zoomScale != 1 ? -1 : THREE.MOUSE.RIGHT
      stage.orbitControl.mouseButtons.PAN =
        zoomScale != 1 ? THREE.MOUSE.LEFT : -1
    } else {
      target.pageWidth = Math.round(pageWidth)
      target.fullWidth = target.pageWidth * 2
      target.height = Math.round(pageHeight)
      const shiftH = (target.shiftHeight = Math.round(
        limitAt(
          (zoomHeight - finalStageHeight + paddingVertical) / 2,
          0,
          zoomHeight
        )
      ))
      const shiftW = (target.shiftWidth = Math.round(
        limitAt(
          (wrapperWidth - availableWidth + paddingHorizontal) / 2,
          0,
          wrapperWidth
        )
      ))
      if (zoomScale == 1) {
        target.left = 0
        target.top = 0
      }
      target.stage.css({
        top: -shiftH,
        bottom: -shiftH,
        right: -shiftW + (isRTL ? sideMenuWidth : 0),
        left: -shiftW + (isRTL ? 0 : sideMenuWidth),
        paddingTop: paddingTop,
        paddingRight: paddingRight,
        paddingBottom: paddingBottom,
        paddingLeft: paddingLeft,
        transform: 'translate3d(' + target.left + 'px,' + target.top + 'px,0)',
      })
      target.stageHeight = stage.height()
      target.wrapper.css({
        width: wrapperWidth,
        height: zoomHeight,
        marginTop:
          finalStageHeight - zoomHeight - paddingVertical > 0
            ? (finalStageHeight - paddingVertical - zoomHeight) / 2
            : 0,
      })
      const wrapperSize = Math.floor(
        distOrigin(pageWidth, pageHeight) * zoomScale
      )
      target.stage
        .find('.df-page-wrapper')
        .width(wrapperSize)
        .height(wrapperSize)
      target.stage
        .find(
          '.df-book-page, .df-page-front, .df-page-back, .df-page-fold-inner-shadow'
        )
        .height(zoomHeight)
        .width(zoomWidth)
    }
    self.checkCenter({ type: 'resize' })
    if (zoomScale == 1) {
      target.container.removeClass('df-zoom-enabled')
    }
    self.pendingZoom = false
  }

  setPageMode(isSingle) {
    if (isSingle == true) {
      this.ui.pageMode.addClass(this.options.icons['doublepage'])
      this.ui.pageMode.html(
        '<span>' + this.options.text.doublePageMode + '</span>'
      )
      this.ui.pageMode.attr('title', this.options.text.doublePageMode)
      this.target.pageMode = PAGE_MODE.SINGLE
    } else {
      this.ui.pageMode.removeClass(this.options.icons['doublepage'])
      this.ui.pageMode.html(
        '<span>' + this.options.text.singlePageMode + '</span>'
      )
      this.ui.pageMode.attr('title', this.options.text.singlePageMode)
      this.target.pageMode = PAGE_MODE.DOUBLE
    }
    if (this.target && this.target.singlePageMode == SINGLE_PAGE_MODE.BOOKLET) {
      this.target.reset()
    }
    this.resize()
  }

  height(val) {
    if (val == null) return this.container.height()
    this.options.height = val
    this.container.height(val)
    this.resize()
  }

  checkCenter(event) {
    event = event || {}
    this.centerType = this.centerType || 'start'
    const target = this.target
    let offsetX = 0,
      xLeft = 0,
      xRight = 0
    const basePage = getBasePage(target._activePage)
    const isEven = target._activePage % 2 == 0
    const isRTL = target.direction == DIRECTION.RTL
    const isSingle = target.pageMode == PAGE_MODE.SINGLE
    const isBooklet =
      isSingle && target.singlePageMode == SINGLE_PAGE_MODE.BOOKLET
    const stageWidth = target.stage.width()
    let wrapperWidth

    if (target.mode == 'css') {
      wrapperWidth = target.wrapper.width()
      offsetX = Math.max((wrapperWidth - stageWidth) / 2, 0)
      xLeft = -wrapperWidth / 4
      xRight = wrapperWidth / 4
      if (basePage == 0 || isBooklet) {
        target.wrapper.css({
          left: isSingle
            ? isRTL
              ? xRight - offsetX
              : xLeft - offsetX
            : isRTL
              ? xRight
              : xLeft,
        })
        target.shadow.css({
          width: '50%',
          left: isRTL ? 0 : '50%',
          transitionDelay: '',
        })
      } else if (basePage == target.pageCount) {
        target.wrapper.css({
          left: isSingle
            ? isRTL
              ? xLeft - offsetX
              : xRight - offsetX
            : isRTL
              ? xLeft
              : xRight,
        })
        target.shadow.css({
          width: '50%',
          left: isRTL ? '50%' : 0,
          transitionDelay: '',
        })
      } else {
        target.wrapper.css({
          left: isSingle
            ? isRTL
              ? isEven
                ? xLeft - offsetX
                : xRight - offsetX
              : isEven
                ? xRight - offsetX
                : xLeft - offsetX
            : 0,
        })
        target.shadow.css({
          width: '100%',
          left: 0,
          transitionDelay: parseInt(target.duration, 10) + 50 + 'ms',
        })
      }
      target.wrapper.css({ transition: event.type == 'resize' ? 'none' : '' })
    } else if (target.stage != null) {
      const stage = target.stage
      const currentX = target.position.x
      let targetX
      wrapperWidth = target.width || target.pageWidth * 2 || 1000

      const a = -wrapperWidth / 2
      const o = wrapperWidth / 2

      if (basePage == 0 || isBooklet) {
        targetX = isRTL ? o : a
      } else if (basePage == target.pageCount) {
        targetX = isRTL ? a : o
      } else {
        targetX = isSingle ? (isRTL ? (isEven ? a : o) : isEven ? o : a) : 0
      }

      const bookX = targetX
      const lightX = -220 + bookX // Move light in sync with book to preserve relative illumination
      const duration = parseInt(this.options.duration, 10) || 800

      if (bookX !== this.centerEnd) {
        if (this.centerTween) this.centerTween.stop()
        this.centerTween = new TWEEN.Tween({
          x: currentX,
          lx: stage.spotLight.position.x,
        })
          .delay(0)
          .to({ x: bookX, lx: lightX }, duration)
          .onUpdate(function () {
            target.position.x = this.x
            stage.cssScene.position.x = this.x
            stage.spotLight.position.x = this.lx
          })
          .easing(target.ease)
          .start()
        this.centerEnd = bookX
      }
    }
  }

  width(val) {
    if (val == null) return this.container.width()
    this.options.width = val
    this.container.width(val)
    this.resize()
  }
}
