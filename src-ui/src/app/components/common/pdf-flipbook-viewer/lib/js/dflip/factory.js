/**
 * DFlip Factory Class
 */

import { SINGLE_PAGE_MODE } from './constants.js'
import { PreviewObject } from './core/preview-object.js'
import { PreviewStage } from './core/preview-stage.js'
import { TextureLibrary } from './core/texture-library.js'
import { Book } from './core/book.js'
import { BookCSS } from './core/book-css.js'
import { FlipBookUI } from './ui/ui.js'
import { hasWebgl } from './utils.js'
import { TWEEN } from './tween.js'

export class FlipBook extends PreviewObject {
  constructor(container, source, options) {
    super(options)
    const self = this
    const $ = jQuery
    self.type = 'FlipBook'
    self.container = $(container)
    self.options = options
    self.options.source = source
    self.contentSource = source

    if (options.height != null && options.height.toString().indexOf('%') < 0) {
      self.container.height(Math.min(options.height, $(window).height()))
    } else {
      self.container.height(options.height)
    }

    if (options.pageSize == 2) {
      // DOUBLEINTERNAL
      if (Array.isArray(self.contentSource)) {
        self.options.singlePageMode = SINGLE_PAGE_MODE.ZOOM
      }
      self.container.addClass('df-double-internal')
    }

    const useWebgl = options.webgl == true && hasWebgl == true
    self.webgl = useWebgl

    self.container.addClass(
      'df-container df-init df-floating df-controls-' +
        self.options.controlsPosition
    )

    if (options.transparent == true) self.container.addClass('df-transparent')
    if (options.direction == 2) self.container.addClass('df-rtl') // RTL

    // Old browser checks would go here

    const bg = options.backgroundImage
      ? `url('${options.backgroundImage}')`
      : ''
    self.container.css({
      position: 'relative',
      overflow: 'hidden',
      backgroundColor: options.backgroundColor,
      backgroundImage: bg,
    })

    self.init(useWebgl, source)

    if (options.onCreate != null) options.onCreate(self)
  }

  init(useWebgl, source) {
    const self = this
    const options = self.options
    const $ = jQuery

    if (useWebgl) {
      // Load 3D dependencies
      const load3D = (callback) => {
        if (window.MOCKUP == null) {
          // Script loading logic here (Three.js, Mockup.js)
          // For refactoring, assuming they are loaded via app.js
          if (callback) callback()
        } else {
          if (callback) callback()
        }
      }

      load3D(() => {
        // Restore critical optimization settings
        const applyOptimizations = () => {
          if (window.MOCKUP) {
            MOCKUP.defaults.anisotropy = 0
            MOCKUP.defaults.groundTexture = 'blank'
          }
          if (window.THREE) {
            THREE.skipPowerOfTwo = true
          }
        }

        applyOptimizations()
        // Robust check: apply optimizations repeatedly for a short period to handle lazy loading
        const optInterval = setInterval(applyOptimizations, 100)
        setTimeout(() => clearInterval(optInterval), 2000)

        self.container.css({ minHeight: 300, minWidth: 300 })
        self.stage = new PreviewStage({ ...options, container: self.container })
        self.stage.previewObject = self
        self.contentProvider = new TextureLibrary(
          source,
          (cp) => {
            const bookOptions = {
              ...options,
              pageCount: cp.pageCount,
              stackCount: 6,
              segments: 20,
              width: cp.bookSize.width,
              height: cp.bookSize.height,
            }
            self.target = self.stage.target = new Book(bookOptions, self.stage)
            self.target.previewObject = self
            self.target.reset = () => {
              self.target.children.forEach((c) => {
                c.skipFlip = true
                c.name = '-2'
              })
              self.contentProvider.annotedPage = '-2'
              self.target.refresh()
            }

            new FlipBookUI(self.container, self)
            self.target.ui = self.ui
            self.target.container = self.container
            cp.webgl = true
            cp.setTarget(self.target)

            self.target.getContentLayer = (idx) => {
              const isRTL = self.target.direction == 2
              const divLeft = self.stage.cssScene.divLeft.element
              const divRight = self.stage.cssScene.divRight.element
              if (isBookletMode(self.target)) return isRTL ? divLeft : divRight
              return idx % 2 == 0
                ? isRTL
                  ? divRight
                  : divLeft
                : isRTL
                  ? divLeft
                  : divRight
            }

            self.target.stage = self.stage
            self.target.flipCallback = () => {
              if (self.contentProvider) {
                self.contentProvider.review('flipCallback')
                // Rotation/position updates for CSS layers in 3D
                if (options.onFlip) options.onFlip(self)
              }
            }

            self.target.updatePageCallback = () => {
              const currentPage = self.target._activePage
              if (self.ui) self.ui.update()
              self.checkCenter()
              self.stage.renderRequestPending = true
              if (window.saveLastPage)
                window.saveLastPage(options.pdfId, currentPage)
              $('#storedPage').text(currentPage)
            }

            const $divLeft = $(self.stage.cssScene.divLeft.element)
            const $divRight = $(self.stage.cssScene.divRight.element)

            self.target.preFlipCallback = () => {
              $divLeft.empty()
              $divRight.empty()
              if (options.beforeFlip) options.beforeFlip(self)
            }

            $(window).trigger('resize')
            $divLeft.css({
              width: cp.bookSize.width,
              height: cp.bookSize.height,
              left: -cp.bookSize.width / 2,
            })
            $divRight.css({
              width: cp.bookSize.width,
              height: cp.bookSize.height,
              left: cp.bookSize.width / 2,
            })

            self.target.ease = TWEEN.Easing.Cubic.InOut
            self.target.contentProvider = cp
            self.target.duration = options.duration
            self.target.gotoPage(self.target._activePage)
            self.target.flipCallback()

            // Auto-trigger resize to unblock rendering (simulates opening dev tools)
            setTimeout(() => {
              $(window).trigger('resize')
              self.resize()
            }, 100)

            if (options.onReady) options.onReady(self)
          },
          options
        )
      })
    } else {
      // 2D/CSS implementation
      self.contentProvider = new TextureLibrary(
        source,
        (cp) => {
          const cssOptions = {
            ...options,
            pageCount: cp.pageCount,
            contentSourceType: cp.contentSourceType,
          }
          self.target = new BookCSS(cssOptions, self.container)
          self.target.previewObject = self
          self.target.reset = () => {
            self.target.children.forEach((c) => {
              c.skipFlip = true
              c.name = '-2'
            })
            self.contentProvider.annotedPage = '-2'
            self.target.refresh()
          }

          new FlipBookUI(self.container, self)
          cp.webgl = false
          cp.setTarget(self.target)
          cp.waitPeriod = 2

          self.target.ease = TWEEN.Easing.Quadratic.InOut
          self.target.duration = options.duration
          self.target.container = self.container

          self.target.updatePageCallback = () => {
            const currentPage = self.target._activePage
            if (self.ui) self.ui.update()
            self.checkCenter()
            if (window.saveLastPage)
              window.saveLastPage(options.pdfId, currentPage)
            $('#storedPage').text(currentPage)
          }

          self.target.resize = () => self.resize()
          $(window).trigger('resize')

          self.target.flipCallback = () => {
            if (self.contentProvider) {
              self.contentProvider.review('flipCallback')
              if (options.onFlip) options.onFlip(self)
            }
          }

          self.target.preFlipCallback = () => {
            if (options.beforeFlip) options.beforeFlip(self)
          }

          self.target.gotoPage(self.target._activePage)
          self.target.flipCallback()
          if (options.onReady) options.onReady(self)
        },
        options
      )
    }
  }

  next() {
    if (this.target && this.target.next) this.target.next()
  }

  prev() {
    if (this.target && this.target.prev) this.target.prev()
  }
}

// Helper to maintain original DFLIP.isBookletMode check
function isBookletMode(target) {
  return target.pageMode == 1 && target.singlePageMode == 2
}
