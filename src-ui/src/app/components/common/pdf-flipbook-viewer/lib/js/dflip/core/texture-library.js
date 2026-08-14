/**
 * DFlip Texture Library Class
 */

import { SOURCE_TYPE, PAGE_SIZE, VERSION } from '../constants.js'
import {
  httpsCorrection,
  log,
  nearestPowerOfTwo,
  getBasePage,
  isBookletMode,
  isRTLMode,
  limitAt,
  createObjectURL,
  getScript,
} from '../utils.js'
import { PDFLinkService } from '../features/pdf-link-service.js'

export class TextureLibrary {
  constructor(source, callback, options) {
    const self = this
    options = options || {}
    self.contentRawSource = source || [options.textureLoadFallback]
    self.contentSource = self.contentRawSource
    self.contentSourceType = null
    self.minDimension = options.minTextureSize || 256
    self.maxDimension = options.maxTextureSize || 2048
    self.pdfRenderQuality = options.pdfRenderQuality || 0.9
    self.waitPeriod = 50
    self.maxLength = 297
    self.zoomScale = 1
    self.maxZoom = 2
    self.options = options
    self.isCrossOrigin = options.isCrossOrigin
    self.normalViewport = { height: 297, width: 210, scale: 1 }
    self.viewport = { height: 297, width: 210, scale: 1 }
    self.imageViewport = { height: 297, width: 210, scale: 1 }
    self.bookSize = { height: 297, width: 210 }
    self.zoomViewport = { height: 297, width: 210 }
    self.cacheIndex = 256
    self.cache = []
    self.pageRatio =
      options.pageRatio || self.viewport.width / self.viewport.height
    self.textureLoadTimeOut = null
    self.type = 'TextureLibrary'

    const $ = jQuery

    if (Array.isArray(self.contentSource)) {
      self.contentSourceType = SOURCE_TYPE.IMAGE
      self.pageCount = self.contentSource.length
      for (let i = 0; i < self.contentSource.length; i++) {
        self.contentSource[i] = httpsCorrection(
          self.contentSource[i].toString()
        )
      }
      $('<img/>')
        .attr('src', self.contentSource[0])
        .on('load', function () {
          self.viewport.height = this.height
          self.viewport.width = this.width
          self.pageRatio = self.viewport.width / self.viewport.height
          self.bookSize = {
            width: (self.pageRatio > 1 ? 1 : self.pageRatio) * self.maxLength,
            height: self.maxLength / (self.pageRatio < 1 ? 1 : self.pageRatio),
          }
          self.zoomViewport = {
            width:
              (self.pageRatio > 1 ? 1 : self.pageRatio) * self.maxDimension,
            height:
              self.maxDimension / (self.pageRatio < 1 ? 1 : self.pageRatio),
          }
          self.linkService = new PDFLinkService()
          $(this).off()
          if (self.options.pageSize == PAGE_SIZE.DOUBLEINTERNAL) {
            self.pageCount = self.contentSource.length * 2 - 2
            if (self.options.webgl == true)
              self.requiresImageTextureScaling = true
          }
          if (callback != null) {
            callback(self)
            callback = null
          }
          log(this.height + ':' + this.width)
        })
    } else if (typeof self.contentSource == 'string') {
      const loadBase64 = () => {
        if (self.contentSource.indexOf('.base64') > 1) {
          $.ajax({
            url: self.contentSource,
            success: (data) => {
              self.options.docParameters = { data: atob(data) }
              loadPdf()
            },
          })
        } else {
          loadPdf()
        }
      }

      const loadPdf = () => {
        if (!self) return
        // console.log("[DFlip] Setting Worker Path:", options.pdfjsWorkerSrc);
        pdfjsLib.GlobalWorkerOptions.workerSrc = options.pdfjsWorkerSrc
        self.contentSourceType = SOURCE_TYPE.PDF
        const o = (self.loading = pdfjsLib.getDocument(
          self.options.docParameters
            ? self.options.docParameters
            : {
                url: httpsCorrection(source),
                rangeChunkSize: isNaN(self.options.rangeChunkSize)
                  ? 524288
                  : self.options.rangeChunkSize,
                cMapUrl: options.cMapUrl,
                cMapPacked: true,
                imageResourcesPath: options.imageResourcesPath,
                disableAutoFetch: true,
                disableStream: true,
                disableFontFace: self.options.disableFontFace,
              }
        ))
        o.promise.then(
          (pdf) => {
            self.pdfDocument = pdf
            pdf.getPage(1).then((page) => {
              self.normalViewport = page.getViewport({ scale: 1 })
              self.viewport = page.getViewport({ scale: 1 })
              self.viewport.height = self.viewport.height / 10
              self.viewport.width = self.viewport.width / 10
              self.pageRatio = self.viewport.width / self.viewport.height
              self.bookSize = {
                width:
                  (self.pageRatio > 1 ? 1 : self.pageRatio) * self.maxLength,
                height:
                  self.maxLength / (self.pageRatio < 1 ? 1 : self.pageRatio),
              }
              self.zoomViewport = {
                width:
                  (self.pageRatio > 1 ? 1 : self.pageRatio) * self.maxDimension,
                height:
                  self.maxDimension / (self.pageRatio < 1 ? 1 : self.pageRatio),
              }
              self.refPage = page
              if (pdf.numPages > 1) {
                pdf.getPage(2).then((page2) => {
                  if (self.options.pageSize == PAGE_SIZE.AUTO) {
                    const vp = page2.getViewport({ scale: 1 })
                    const ratio = vp.width / vp.height
                    if (ratio > self.pageRatio * 1.5) {
                      self.options.pageSize = PAGE_SIZE.DOUBLEINTERNAL
                      self.pageCount = pdf.numPages * 2 - 2
                    } else {
                      self.options.pageSize = PAGE_SIZE.SINGLE
                    }
                  }
                  if (callback != null) {
                    callback(self)
                    callback = null
                  }
                })
              } else {
                if (callback != null) {
                  callback(self)
                  callback = null
                }
              }
            })
            self.linkService = new PDFLinkService()
            self.linkService.setDocument(pdf, null)
            self.pageCount = pdf.numPages
            self.contentSource = pdf
          },
          () => {
            if (self) {
              console.error('Cannot access PDF file', self.contentSource)
            }
          }
        )
      }

      const loadWorker = () => {
        if (!self) return
        if (options.pdfjsWorkerSrc.indexOf('?ver') < 0)
          options.pdfjsWorkerSrc += '?ver=' + VERSION
        const a = document.createElement('a')
        a.href = options.pdfjsWorkerSrc
        if (a.hostname !== window.location.hostname && a.hostname !== '') {
          $.ajax({
            url: options.pdfjsWorkerSrc,
            cache: true,
            success: (data) => {
              options.pdfjsWorkerSrc = createObjectURL(data, 'text/javascript')
              loadBase64()
            },
          })
        } else {
          loadBase64()
        }
      }

      if (window.pdfjsLib == null) {
        getScript(
          options.pdfjsSrc + '?ver=' + VERSION,
          () => {
            loadWorker()
          },
          () => {
            console.error('Unable to load PDF service.')
          }
        )
      } else {
        loadWorker()
      }
    } else {
      console.error('Unknown source type. Please check documentation for help')
    }

    this.dispose = () => {
      if (self.loading && self.loading.destroy) {
        self.loading.destroy()
      }
      self.loading = null
      if (self.textureLoadTimeOut) {
        clearTimeout(self.textureLoadTimeOut)
        self.textureLoadTimeOut = null
      }
      if (this.targetObject) {
        if (this.targetObject.dispose) this.targetObject.dispose()
        this.targetObject.processPage = null
        this.targetObject.requestPage = null
        if (this.targetObject.container) this.targetObject.container.off()
      }
      if (this.pdfDocument) this.pdfDocument.destroy()
      if (this.linkService) this.linkService.dispose()
      this.targetObject = null
      this.pdfDocument = null
      this.linkService = null
    }
  }

  checkViewportSize(width, height, scale) {
    const self = this
    const target = self.targetObject
    const cacheIdx = self.cacheIndex

    if (self.contentSourceType == SOURCE_TYPE.PDF) {
      self.cacheIndex = Math.floor(Math.max(width * scale, height * scale))
      self.cacheIndex = limitAt(
        self.cacheIndex * (window.devicePixelRatio || 1),
        self.minDimension,
        self.maxDimension
      )

      if (self.cache[self.cacheIndex] == null) self.cache[self.cacheIndex] = []
      if (cacheIdx !== self.cacheIndex) {
        target.refresh()
      }
      self.imageViewport = self.refPage.getViewport({
        scale: (height * scale) / self.normalViewport.height,
      })
      self.viewport =
        target.mode == 'css'
          ? self.imageViewport
          : self.refPage.getViewport({
              scale: self.bookSize.height / self.normalViewport.height,
            })
      self.annotedPage = undefined
      self.review()
    } else {
      if (self.cache[self.cacheIndex] == null) self.cache[self.cacheIndex] = []
    }
  }

  getCache(idx) {
    return this.cache[this.cacheIndex] ? this.cache[this.cacheIndex][idx] : null
  }

  setCache(idx, data, forcedIdx) {
    const cacheIdx = forcedIdx || this.cacheIndex
    if (!this.cache[cacheIdx]) this.cache[cacheIdx] = []
    this.cache[cacheIdx][idx] = data
  }

  setTarget(target) {
    const self = this
    if (target == null) return this.targetObject
    this.targetObject = target
    target.contentProvider = this
    target.container.removeClass('df-init')
    if (self.linkService != null) {
      self.linkService.setViewer(target)
    }
    target.processPage = (idx, callback) => {
      if (idx > 0 && idx <= self.pageCount) {
        self.getPage(idx, callback)
      } else {
        self.setPage(idx, self.options.textureLoadFallback, callback)
      }
    }
    target.requestPage = () => {
      self.review('Request')
    }
    if (target.resize != null) target.resize()
  }

  review(reason) {
    const self = this
    clearTimeout(self.textureLoadTimeOut)
    self.textureLoadTimeOut = setTimeout(() => {
      self.textureLoadTimeOut = setTimeout(
        () => self.reviewPages(self, reason),
        self.waitPeriod / 2
      )
    }, self.waitPeriod)
  }

  reviewPages(self, reason) {
    const target = self.targetObject
    if (!target) return
    const isBooklet = isBookletMode(target)
    let isFlipping = false

    for (let i = 0; i < target.children.length; i++) {
      if (target.children[i].isFlipping) {
        isFlipping = true
        break
      }
    }

    if (!isFlipping) {
      const numVisible = Math.min(target.children.length, 3)
      const activeIdx = isBooklet
        ? target._activePage
        : getBasePage(target._activePage)
      self.baseNumber = activeIdx
      const range = self.zoomScale > 1 ? 1 : numVisible

      for (let i = 0; i < range; i++) {
        const offset = Math.floor(i / 2)
        const delta =
          i % 2 == 0
            ? -offset * (isBooklet ? 1 : 2)
            : (offset == 0 ? 1 : offset) * (isBooklet ? 1 : 2)
        const p1 = activeIdx + delta,
          p2 = activeIdx + delta + 1
        const page1 = target.getPageByNumber(p1),
          page2 = target.getPageByNumber(p2)
        const stamp1 = p1 + '|' + self.cacheIndex,
          stamp2 = p2 + '|' + self.cacheIndex
        let loaded = 0

        if (page1 && page1.frontPageStamp != stamp1 && page1.visible) {
          page1.frontTextureLoaded = false
          target.processPage(p1, () => self.review('Batch Call'))
          page1.frontPageStamp = stamp1
          loaded++
        }
        if (
          page2 &&
          page2.backPageStamp != stamp2 &&
          page2.visible &&
          !isBooklet
        ) {
          page2.backTextureLoaded = false
          target.processPage(p2, () => self.review('Batch Call'))
          page2.backPageStamp = stamp2
          loaded++
        }

        if (delta == 0 && self.annotedPage !== activeIdx) {
          self.getAnnotations(p1)
          if (!isBooklet) self.getAnnotations(p2)
          self.annotedPage = activeIdx
        }
        if (loaded > 0) break
      }
    } else {
      self.review('Revisit request')
    }
  }

  getPage(idx, callback) {
    const self = this
    const pageIdx = parseInt(idx, 10)
    let sourceIdx = pageIdx
    const source = self.contentSource

    if (pageIdx <= 0 && pageIdx >= self.pageCount) {
      self.setPage(pageIdx, self.options.textureLoadFallback, callback)
    } else {
      const cached = self.getCache(pageIdx)
      if (cached) {
        self.setPage(pageIdx, cached, callback)
      } else {
        if (self.options.pageSize == PAGE_SIZE.DOUBLEINTERNAL && pageIdx > 2) {
          sourceIdx = Math.ceil((pageIdx - 1) / 2) + 1
        }

        if (self.contentSourceType == SOURCE_TYPE.PDF) {
          source.getPage(sourceIdx).then((page) => {
            renderPdfPage(page, pageIdx, callback)
          })
        } else {
          const imgSrc = source[sourceIdx - 1]
          const img = new Image()
          if (self.isCrossOrigin) img.crossOrigin = 'Anonymous'
          img.onload = () => {
            self.setCache(pageIdx, imgSrc, self.cacheIndex)
            self.setPage(pageIdx, imgSrc, callback)
            if (callback) callback()
          }
          img.src = imgSrc
        }
      }
    }

    function renderPdfPage(page, idx, callback) {
      const forceFit = self.options.forceFit
      const isInternalDouble =
        self.options.pageSize == PAGE_SIZE.DOUBLEINTERNAL &&
        idx > 1 &&
        idx < self.pageCount
      const ratio = isInternalDouble && forceFit ? 2 : 1
      const baseViewport = forceFit
        ? page.getViewport({ scale: 1 })
        : self.normalViewport
      let scale =
        self.cacheIndex /
        Math.max(baseViewport.width / ratio, baseViewport.height)

      if (self.webgl) {
        scale =
          nearestPowerOfTwo(self.cacheIndex) /
          (self.pageRatio > 1
            ? baseViewport.width / ratio
            : baseViewport.height)
      }

      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      canvas.height = Math.round(baseViewport.height * scale)
      canvas.width = Math.round((baseViewport.width / ratio) * scale)

      if (
        self.targetObject.mode == 'css' &&
        Math.abs(self.targetObject.zoomHeight - canvas.height) < 2
      ) {
        canvas.height = self.targetObject.zoomHeight
        canvas.width = self.targetObject.zoomWidth
      }

      const viewport = page.getViewport({ scale })
      if (isInternalDouble) {
        if (isRTLMode(self.targetObject)) {
          if (idx % 2 == 0) viewport.transform[4] = -canvas.width
        } else {
          if (idx % 2 == 1) viewport.transform[4] = -canvas.width
        }
      }

      page.cleanupAfterRender = true
      page.render({ canvasContext: ctx, viewport }).promise.then(() => {
        if (self.options.canvasToBlob && !self.webgl) {
          canvas.toBlob(
            (blob) => {
              const url = URL.createObjectURL(blob)
              self.setCache(idx, url, self.cacheIndex)
              self.setPage(idx, url, callback)
            },
            'image/jpeg',
            self.pdfRenderQuality
          )
        } else {
          self.setPage(idx, canvas, callback)
        }
      })
    }
  }

  getAnnotations(idx) {
    const self = this
    const $ = jQuery
    if (self.options.enableAnnotation == false) return
    const target = self.targetObject
    const pageIdx = parseInt(idx, 10)
    const layer = $(target.getContentLayer(pageIdx))
    layer.empty()

    if (pageIdx > 0 && pageIdx <= self.pageCount) {
      if (self.contentSourceType == SOURCE_TYPE.PDF) {
        let srcIdx = pageIdx
        if (self.options.pageSize == PAGE_SIZE.DOUBLEINTERNAL && pageIdx > 2) {
          srcIdx = Math.ceil((pageIdx - 1) / 2) + 1
        }
        self.contentSource.getPage(srcIdx).then((page) => {
          if (layer.length > 0) {
            const vp = page.getViewport({
              scale:
                self.viewport.height / page.getViewport({ scale: 1 }).height,
            })
            self.setupAnnotations(page, vp, layer, pageIdx)
          }
        })
      }
      // Custom links and HTML annotations could be added here
    }
  }

  setPage(idx, data, callback) {
    const self = this
    const target = self.targetObject
    const isRTL = isRTLMode(target)
    const isBooklet = isBookletMode(target)

    const page = target.getPageByNumber(idx)
    if (page) {
      const isBack =
        (idx % 2 != 0 && !isRTL) ||
        (idx % 2 != 1 && isRTL && !isBooklet) ||
        (isBooklet && !isRTL)
      if (isBack) {
        page.backImage(data, (img, tex) => {
          page.backTextureLoaded = true
          if (
            self.requiresImageTextureScaling &&
            tex &&
            idx != 1 &&
            idx != self.pageCount
          ) {
            tex.repeat.x = 0.5
            tex.offset.x = 0.5
          }
          if (callback) callback()
        })
      } else {
        page.frontImage(data, (img, tex) => {
          page.frontTextureLoaded = true
          if (
            self.requiresImageTextureScaling &&
            tex &&
            idx != 1 &&
            idx != self.pageCount
          ) {
            tex.repeat.x = 0.5
          }
          if (callback) callback()
        })
      }
    }
  }

  setupAnnotations(page, viewport, layer, idx) {
    const self = this
    const $ = jQuery
    return page.getAnnotations().then((annotations) => {
      const vp = viewport.clone({ dontFlip: true })
      const $layer = $(layer)
      let annDiv = $layer.find('.annotationDiv')
      if (annDiv.length == 0) {
        annDiv = $("<div class='annotationDiv'>")
        $layer.append(annDiv)
      }
      annDiv.empty()

      if (
        self.options.pageSize == PAGE_SIZE.DOUBLEINTERNAL &&
        idx > 2 &&
        idx % 2 == 1
      ) {
        annDiv.css({ left: '-100%' })
      } else if (idx == 1) {
        annDiv.css({ left: '' })
      }

      pdfjsLib.AnnotationLayer.render({
        annotations,
        div: annDiv[0],
        page,
        viewport: vp,
        imageResourcesPath: self.options.imageResourcesPath,
        linkService: self.linkService,
      })

      if (self.options.annotationClass) {
        annDiv.find('> section').addClass(self.options.annotationClass)
      }
    })
  }
}
