/**
 * DFlip Book Class
 */

import { DIRECTION, PAGE_MODE, SINGLE_PAGE_MODE } from '../constants.js'
import {
  isMobile,
  isBookletMode,
  isRTLMode,
  isHardPage,
  limitAt,
} from '../utils.js'
import { BookPaper } from './book-paper.js'

export class Book extends MOCKUP.Bundle {
  constructor(options, mockup) {
    options = options || {}
    options.segments = options.segments || 50
    super(options, mockup)

    this.options = options
    this.pageCount = options.pageCount
    this.height = options.height
    this.width = options.width
    this.direction = options.direction || DIRECTION.LTR
    this.startPage = 1
    this.endPage = this.pageCount
    this.stackCount = options.stackCount || 6
    this.materials = []
    this.angles = [0, 0, 0, 0, 0, 0]
    this.stiffness = options.stiffness == null ? 1.5 : options.stiffness
    this.hardConfig = options.hard
    this._activePage = options.openPage || this.startPage
    this.createStack(options)
    this.pageMode =
      options.pageMode ||
      (isMobile || this.pageCount <= 2 ? PAGE_MODE.SINGLE : PAGE_MODE.DOUBLE)
    this.singlePageMode =
      options.singlePageMode ||
      (isMobile ? SINGLE_PAGE_MODE.BOOKLET : SINGLE_PAGE_MODE.ZOOM)
    this.type = 'Book'
  }

  getPageByNumber(pageNum) {
    const isBooklet = isBookletMode(this)
    const isRTL = isRTLMode(this)
    const idx = isBooklet
      ? isRTL
        ? pageNum + 1
        : pageNum
      : Math.floor((pageNum - 1) / 2)
    return this.getObjectByName(idx.toString())
  }

  isPageHard(pageNum) {
    return isHardPage(this.hardConfig, pageNum, this.pageCount)
  }

  activePage(pageNum) {
    if (pageNum == null) return this._activePage
    this.gotoPage(pageNum)
  }

  gotoPage(pageNum) {
    pageNum = parseInt(pageNum, 10)
    this._activePage = pageNum
    this.updatePage(pageNum)
  }

  moveBy(delta) {
    let targetPage = this._activePage + delta
    targetPage = limitAt(targetPage, this.startPage, this.endPage)
    this.gotoPage(targetPage)
  }

  next(delta) {
    if (delta == null)
      delta = this.direction == DIRECTION.RTL ? -this.pageMode : this.pageMode
    this.moveBy(delta)
  }

  prev(delta) {
    if (delta == null)
      delta = this.direction == DIRECTION.RTL ? this.pageMode : -this.pageMode
    this.moveBy(delta)
  }

  updateAngle() {
    const startAngle = this.angles[1]
    const endAngle = this.angles[4]
    const delta = endAngle - startAngle
    const count = this.stackCount
    for (let i = 0; i < count; i++) {
      const child = this.children[i]
      child.angles[1] = startAngle + (i * delta) / (count * 100)
      child.stiffness = this.stiffness
      child.updateAngle()
    }
  }

  refresh() {
    this.updatePage(this._activePage)
    if (this.flipCallback != null) this.flipCallback()
  }

  updatePage(pageNum) {
    const isRTL = this.direction == DIRECTION.RTL
    const isBooklet = isBookletMode(this)
    const ratio = isBooklet ? 1 : 2
    let normalizedPage = Math.floor(pageNum / ratio)

    if (isRTL)
      normalizedPage = Math.ceil(this.pageCount / ratio) - normalizedPage

    const oldPage = this.oldBaseNumber || 0
    const totalNormalized = this.pageCount / ratio
    const stackCount = this.stackCount
    const step = 0.02
    const depthBase = 0.4
    const stiffnessBase = isBooklet
      ? 0
      : (0.5 -
          Math.abs(totalNormalized / 2 - normalizedPage) / totalNormalized) /
        this.stiffness
    const midIdx = Math.floor(stackCount / 2)
    let shifted = false

    if (oldPage > normalizedPage) {
      shifted = true
      this.children[stackCount - 1].skipFlip = true
      this.children.unshift(this.children.pop())
    } else if (oldPage < normalizedPage) {
      this.children[0].skipFlip = true
      this.children.push(this.children.shift())
    }

    const remainingPages = totalNormalized - normalizedPage
    const factor = 5 / totalNormalized
    const depthLeft = (factor * normalizedPage) / 2
    const depthRight = (factor * remainingPages) / 2
    const maxDepth = depthLeft < depthRight ? depthRight : depthLeft

    for (let i = 0; i < stackCount; i++) {
      const child = this.children[i]
      const currentAngle = child.angles[1]
      let targetAngle
      let pageIdx = normalizedPage - midIdx + i
      if (isRTL)
        pageIdx = isBooklet
          ? this.pageCount - pageIdx
          : Math.ceil(this.pageCount / 2) - pageIdx - 1

      const isHard = (child.isHard = this.isPageHard(pageIdx))
      const oldName = child.name
      child.isEdge = false

      if (i == 0) {
        child.depth = depthLeft < depthBase ? depthBase : depthLeft
      } else if (i == stackCount - 1) {
        child.depth = depthRight < depthBase ? depthBase : depthRight
      } else {
        child.depth = depthBase
        child.isEdge = false
      }

      if (child.isFlipping == true) {
        child.depth = depthBase
      }

      child.position.x = 0
      const angle1 = step * i
      const angle2 = 180 - step * (i - midIdx) + step * i

      if (i < midIdx) {
        child.newStiffness =
          isHard || this.stiffness == 0
            ? 0
            : stiffnessBase / (normalizedPage / totalNormalized) / 4
        targetAngle = angle1
        child.position.z = maxDepth - (-i + midIdx) * depthBase
        if (shifted == true) child.position.z -= depthBase
      } else {
        targetAngle = angle2
        child.newStiffness =
          isHard || this.stiffness == 0
            ? 0
            : stiffnessBase /
              (Math.abs(totalNormalized - normalizedPage) / totalNormalized) /
              4
        child.position.z =
          maxDepth - (-stackCount + i + midIdx + 1) * depthBase - child.depth
      }

      if (child.isFlipping == false) {
        if (
          Math.abs(currentAngle - targetAngle) > 20 &&
          child.skipFlip == false
        ) {
          child.depth = depthBase
          let currentStiffness = child.stiffness
          if (currentAngle > targetAngle) {
            currentStiffness =
              stiffnessBase /
              (Math.abs(totalNormalized - normalizedPage) / totalNormalized) /
              4
          } else {
            currentStiffness =
              stiffnessBase / (normalizedPage / totalNormalized) / 4
          }
          child.position.z += depthBase
          child.stiffness = isNaN(currentStiffness)
            ? child.stiffness
            : currentStiffness
          child.updateAngle(true)
          child.targetStiffness = isHard
            ? 0
            : i < normalizedPage
              ? stiffnessBase /
                (Math.abs(totalNormalized - normalizedPage) / totalNormalized) /
                4
              : stiffnessBase / (normalizedPage / totalNormalized) / 4
          child.targetStiffness = isHard
            ? 0
            : isNaN(child.targetStiffness)
              ? child.stiffness
              : child.targetStiffness
          child.isFlipping = true
          child.tween(currentAngle, targetAngle)
          if (this.preFlipCallback != null) this.preFlipCallback()
        } else {
          child.skipFlip = false
          child.newStiffness = isNaN(child.newStiffness)
            ? 0
            : child.newStiffness
          if (
            child.angles[1] != targetAngle ||
            child.stiffness != child.newStiffness ||
            child.depth != child.oldDepth
          ) {
            child.angles[1] = child.angles[4] = targetAngle
            child.stiffness = child.newStiffness
            child.updateAngle(true)
          }
        }
      }

      child.visible = isBooklet
        ? isRTL
          ? i < midIdx || child.isFlipping
          : i >= midIdx || child.isFlipping
        : (pageIdx >= 0 && pageIdx < totalNormalized) ||
          (isBooklet && pageIdx == totalNormalized)

      if (this.requestPage != null) {
        child.name = pageIdx.toString()
        if (child.name != oldName) {
          child.textureLoaded = false
          const fallback = this.options
            ? this.options.textureLoadFallback
            : 'blank'
          child.frontImage(fallback)
          child.frontPageStamp = '-1'
          child.frontTextureLoaded = false
          child.backImage(fallback)
          child.backPageStamp = '-1'
          child.backTextureLoaded = false
          this.requestPage()
        }
      }

      child.oldDepth = child.depth
      const offsetX =
        Math.abs(child.geometry.boundingBox.max.x) <
        Math.abs(child.geometry.boundingBox.min.x)
          ? child.geometry.boundingBox.max.x
          : child.geometry.boundingBox.min.x
      child.position.x =
        child.isEdge == true && child.isFlipping == false
          ? i < midIdx
            ? offsetX
            : -offsetX
          : 0
    }

    this.oldBaseNumber = normalizedPage
    if (this.updatePageCallback != null) this.updatePageCallback()
  }

  createCover(options) {
    options.width = options.width * 2
    this.cover = new MOCKUP.BiFold(options)
    this.add(this.cover)
  }

  createStack(options) {
    const colors = 'red,green,blue,yellow,orange,black'.split(',')
    for (let i = 0; i < this.stackCount; i++) {
      const pageOptions = { ...options }
      pageOptions.angles = [, this.stackCount - i]
      pageOptions.stiffness = (this.stackCount - i) / 100
      const paper = new BookPaper(pageOptions, this.mockup)
      paper.angles[1] = 180
      paper.index = i
      paper.updateAngle()
      paper.textureReady = false
      paper.textureRequested = false
      this.add(paper)
      paper.color = colors[i]
      paper.position.z = -1 * i
    }
  }

  shininess(val) {
    if (val == null) return this.mainObject.shininess()
    this.mainObject.shininess(val)
  }

  bumpScale(val) {
    if (val == null) return this.mainObject.bumpScale()
    this.mainObject.bumpScale(val)
  }

  frontImage(val) {
    if (val == null) return this.mainObject.frontImage()
    this.mainObject.frontImage(val)
  }

  backImage(val) {
    if (val == null) return this.mainObject.backImage()
    this.mainObject.backImage(val)
  }
}
