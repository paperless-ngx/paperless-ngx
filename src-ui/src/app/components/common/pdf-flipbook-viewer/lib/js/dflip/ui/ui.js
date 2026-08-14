/**
 * DFlip UI Class
 */

import { PAGE_MODE, CONTROLSPOSITION, DIRECTION } from '../constants.js'
import {
  html,
  isRTLMode,
  hasFullscreenEnabled,
  getFullscreenElement,
  log,
} from '../utils.js'

export class FlipBookUI {
  constructor(container, flipbook) {
    const $ = jQuery
    const a = 'df-ui'
    const o = 'df-ui-wrapper'
    const r = a + '-' + 'btn'
    const isRTL = isRTLMode(flipbook.target)
    const ui = (flipbook.ui = $(html.div, { class: a }))
    const options = flipbook.options
    const n = flipbook

    this.ui = ui
    this.options = options
    this.flipbook = flipbook
    this.$ = $

    ui.dispose = () => {
      container.find('.' + r).each(function () {
        $(this).off()
      })
      document.removeEventListener('keyup', this.onKeyUp, false)
      window.removeEventListener('click', this.onWindowClick, false)
      ui.update = null
      n.ui = null
    }

    const validatePage = (page) => {
      if (isNaN(page)) page = n.target._activePage
      else if (page < 1) page = 1
      else if (page > n.target.pageCount) page = n.target.pageCount
      return page
    }

    ui.next = $(html.div, {
      class: r + ' ' + a + '-next ' + options.icons['next'],
      title: isRTL ? options.text.previousPage : options.text.nextPage,
      html: '<span>' + options.text.nextPage + '</span>',
    }).on('click', () => {
      n.next()
    })

    ui.prev = $(html.div, {
      class: r + ' ' + a + '-prev ' + options.icons['prev'],
      title: isRTL ? options.text.nextPage : options.text.previousPage,
      html: '<span>' + options.text.previousPage + '</span>',
    }).on('click', () => {
      n.prev()
    })

    const zoomWrapper = $(html.div, { class: o + ' ' + a + '-zoom' })
    ui.zoomIn = $(html.div, {
      class: r + ' ' + a + '-zoomin ' + options.icons['zoomin'],
      title: options.text.zoomIn,
      html: '<span>' + options.text.zoomIn + '</span>',
    }).on('click', () => {
      n.zoom(1)
      ui.update()
      if (n.target.startPoint && n.target.pan) n.target.pan(n.target.startPoint)
    })

    ui.zoomOut = $(html.div, {
      class: r + ' ' + a + '-zoomout ' + options.icons['zoomout'],
      title: options.text.zoomOut,
      html: '<span>' + options.text.zoomOut + '</span>',
    }).on('click', () => {
      n.zoom(-1)
      ui.update()
      if (n.target.startPoint && n.target.pan) n.target.pan(n.target.startPoint)
    })
    zoomWrapper.append(ui.zoomIn).append(ui.zoomOut)

    ui.pageNumber = $(html.div, { class: r + ' ' + a + '-page' })
    ui.pageInput = $(
      '<input id="df_book_page_number" type="text" class="df-page-input"/>'
    ).appendTo(ui.pageNumber)
    ui.pageSeparator = $('<span class="df-page-separator">/</span>').appendTo(
      ui.pageNumber
    )
    ui.pageTotal = $('<span class="df-page-total"></span>').appendTo(
      ui.pageNumber
    )

    ui.pageInput
      .on('change', () => {
        let e = parseInt(ui.pageInput.val(), 10)
        e = validatePage(e)
        n.gotoPage(e)
      })
      .on('keyup', (e) => {
        e.stopPropagation()
        if (e.keyCode == 13) {
          let t = parseInt(ui.pageInput.val(), 10)
          t = validatePage(t)
          if (t !== validatePage(n.target._activePage || n._activePage))
            n.gotoPage(t)
          ui.pageInput.blur()
        }
      })
      .on('keydown', (e) => {
        e.stopPropagation()
      })
      .on('focus', function () {
        $(this).select()
      })

    const sizeWrapper = $(html.div, { class: o + ' ' + a + '-size' })
    this.onWindowClick = (e) => {
      if (ui.more) ui.more.removeClass('df-active')
    }
    window.addEventListener('click', this.onWindowClick, false)

    ui.more = $(html.div, {
      class: r + ' ' + a + '-more ' + options.icons['more'],
    }).on('click', (e) => {
      if (!ui.more.hasClass('df-active')) {
        $(ui.more).addClass('df-active')
        e.stopPropagation()
      }
    })
    const moreContainer = $(html.div, { class: 'more-container' })
    ui.more.append(moreContainer)

    if (typeof options.source == 'string' && options.enableDownload == true) {
      const downloadClass =
        r + ' ' + a + '-download ' + options.icons['download']
      ui.download = $(
        '<a download target="_blank" class="' +
          downloadClass +
          '"><span>' +
          options.text.downloadPDFFile +
          '</span></a>'
      )
      ui.download
        .attr('href', options.source)
        .attr('title', options.text.downloadPDFFile)
    }

    if (typeof options.source == 'string') {
      ui.print = $(html.div, {
        class: r + ' ' + a + '-print ' + options.icons['print'],
        title: options.text.printPDFFile,
        html: '<span>' + options.text.printPDFFile + '</span>',
      }).on('click', () => {
        const frame = document.createElement('iframe')
        frame.style.position = 'fixed'
        frame.style.right = '0'
        frame.style.bottom = '0'
        frame.style.width = '0'
        frame.style.height = '0'
        frame.style.border = '0'
        frame.onload = () => {
          frame.contentWindow?.focus()
          frame.contentWindow?.print()
        }
        frame.src = options.source
        document.body.appendChild(frame)
      })
    }

    if (!hasFullscreenEnabled()) {
      container.addClass('df-custom-fullscreen')
    }

    ui.switchFullscreen = () => {
      const fullscreenElement = getFullscreenElement()
      const el = n.container[0]
      if (ui.isFullscreen != true) {
        n.container.addClass('df-fullscreen')
        $('body').addClass('df-fullscreen-active')
        if (el.requestFullscreen) {
          el.requestFullscreen()
        } else if (el.msRequestFullscreen) {
          el.msRequestFullscreen()
        } else if (el.mozRequestFullScreen) {
          el.mozRequestFullScreen()
        } else if (el.webkitRequestFullscreen) {
          el.webkitRequestFullscreen()
        }
        ui.isFullscreen = true
      } else {
        n.container.removeClass('df-fullscreen')
        $('body').removeClass('df-fullscreen-active')
        ui.isFullscreen = false
        if (document.exitFullscreen) {
          if (document.fullscreenElement) document.exitFullscreen()
        } else if (document.msExitFullscreen) {
          document.msExitFullscreen()
        } else if (document.mozCancelFullScreen) {
          if (document.fullscreenElement) document.mozCancelFullScreen()
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen()
        }
      }
      if (!hasFullscreenEnabled()) {
        setTimeout(() => {
          n.resize()
        }, 50)
      }
    }

    ui.fullScreen = $(html.div, {
      class: r + ' ' + a + '-fullscreen ' + options.icons['fullscreen'],
      title: options.text.toggleFullscreen,
      html: '<span>' + options.text.toggleFullscreen + '</span>',
    }).on('click', ui.switchFullscreen)

    ui.fit = $(html.div, {
      class: r + ' ' + a + '-fit ' + options.icons['fitscreen'],
    }).on('click', function () {
      $(this).toggleClass('df-button-fit-active')
    })

    sizeWrapper.append(ui.fullScreen)
    const controlsWrapper = $(html.div, {
      class: o + ' ' + a + '-controls',
      style: 'display:none !important;',
    })

    ui.startPage = $(html.div, {
      class:
        r +
        ' ' +
        a +
        '-start ' +
        (isRTL ? options.icons['end'] : options.icons['start']),
      title: options.text.gotoFirstPage,
      html: '<span>' + options.text.gotoFirstPage + '</span>',
    }).on('click', () => {
      n.start()
    })

    ui.endPage = $(html.div, {
      class:
        r +
        ' ' +
        a +
        '-end ' +
        (isRTL ? options.icons['start'] : options.icons['end']),
      title: options.text.gotoLastPage,
      html: '<span>' + options.text.gotoLastPage + '</span>',
    }).on('click', () => {
      n.end()
    })

    ui.pageMode = $(html.div, {
      class: r + ' ' + a + '-pagemode ' + options.icons['singlepage'],
      html: '<span>' + options.text.singlePageMode + '</span>',
    }).on('click', function () {
      const e = $(this)
      n.setPageMode(!e.hasClass(options.icons['doublepage']))
    })
    n.setPageMode(n.target.pageMode == PAGE_MODE.SINGLE)

    ui.altPrev = $(html.div, {
      class: r + ' ' + a + '-prev' + ' ' + a + '-alt ' + options.icons['prev'],
      title: isRTL ? options.text.nextPage : options.text.previousPage,
      html: '<span>' + options.text.previousPage + '</span>',
    }).on('click', () => {
      n.prev()
    })

    ui.altNext = $(html.div, {
      class: r + ' ' + a + '-next' + ' ' + a + '-alt ' + options.icons['next'],
      title: isRTL ? options.text.previousPage : options.text.nextPage,
      html: '<span>' + options.text.nextPage + '</span>',
    }).on('click', () => {
      n.next()
    })

    const allControls = options.allControls.replace(/ /g, '').split(',')
    const moreControls = ',' + options.moreControls.replace(/ /g, '') + ','
    let hideControls = ',' + options.hideControls.replace(/ /g, '') + ','

    // Re-check mobile fullscreen
    if (
      /(iPad|iPhone|iPod)/g.test(navigator.userAgent) &&
      /mobile/i.test(navigator.userAgent)
    ) {
      hideControls += ',fullScreen,'
    }

    for (let i = 0; i < allControls.length; i++) {
      const controlName = allControls[i]
      if (hideControls.indexOf(',' + controlName + ',') < 0) {
        const controlEl = ui[controlName]
        if (controlEl != null && typeof controlEl == 'object') {
          if (
            moreControls.indexOf(',' + controlName + ',') > -1 &&
            controlName !== 'more' &&
            controlName !== 'pageNumber'
          ) {
            moreContainer.append(controlEl)
          } else {
            controlsWrapper.append(controlEl)
          }
        }
      }
    }

    container
      .append(controlsWrapper)
      .append(ui.prev)
      .append(ui.next)
      .append(zoomWrapper)

    this.onKeyUp = (e) => {
      const ESC = 27
      const LEFT = 37
      const RIGHT = 39
      switch (e.keyCode) {
        case ESC:
          if (ui.isFullscreen == true) {
            ui.fullScreen.trigger('click')
          }
          break
        case LEFT:
          n.prev()
          break
        case RIGHT:
          n.next()
          break
      }
    }
    document.addEventListener('keyup', this.onKeyUp, false)

    ui.update = (resize) => {
      log('ui update')
      const target = n.target
      const currentPage = validatePage(target._activePage || n._activePage)
      const totalPages = target.pageCount || n.pageCount
      const isRTL = target.direction == DIRECTION.RTL
      const isFirst = currentPage == 1 || currentPage == 0
      const isLast = currentPage == totalPages

      ui.next.show()
      ui.prev.show()
      ui.altNext.removeClass('disabled')
      ui.altPrev.removeClass('disabled')

      if ((isFirst && !isRTL) || (isLast && isRTL)) {
        ui.prev.hide()
        ui.altPrev.addClass('disabled')
      }
      if ((isLast && !isRTL) || (isFirst && isRTL)) {
        ui.next.hide()
        ui.altNext.addClass('disabled')
      }

      if (!ui.pageInput.is(':focus')) {
        ui.pageInput.val(currentPage)
      }
      ui.pageTotal.html(totalPages)

      if (resize == true) n.resize()

      if (target.contentProvider.zoomScale == target.contentProvider.maxZoom) {
        ui.zoomIn.addClass('disabled')
      } else {
        ui.zoomIn.removeClass('disabled')
      }

      if (target.contentProvider.zoomScale == 1) {
        ui.zoomOut.addClass('disabled')
      } else {
        ui.zoomOut.removeClass('disabled')
      }
    }

    if (n.target != null) {
      n.target.ui = ui
    }
    if (options.onCreateUI != null) options.onCreateUI(n)
  }
}
