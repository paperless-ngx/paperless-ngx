/**
 * DFlip PDF Link Service Class
 */

import { PAGE_SIZE, LINK_TARGET } from '../constants.js'

export class PDFLinkService {
  constructor() {
    this.baseUrl = null
    this.pdfDocument = null
    this.pdfViewer = null
    this.pdfHistory = null
    this._pagesRefCache = null
  }

  dispose() {
    this.baseUrl = null
    this.pdfDocument = null
    this.pdfViewer = null
    this.pdfHistory = null
    this._pagesRefCache = null
  }

  setDocument(pdfDocument, baseUrl) {
    this.baseUrl = baseUrl
    this.pdfDocument = pdfDocument
    this._pagesRefCache = Object.create(null)
  }

  setViewer(pdfViewer) {
    this.pdfViewer = pdfViewer
    this.externalLinkTarget = pdfViewer.previewObject.options.linkTarget
  }

  setHistory(pdfHistory) {
    this.pdfHistory = pdfHistory
  }

  get pagesCount() {
    return this.pdfDocument.numPages
  }

  get page() {
    return this.pdfViewer.currentPageNumber
  }

  set page(val) {
    this.pdfViewer.currentPageNumber = val
  }

  navigateTo(dest) {
    let goToHash = ''
    const n = this

    const navigate = (destination) => {
      let pageNumber =
        destination instanceof Object
          ? n._pagesRefCache[destination.num + ' ' + destination.gen + ' R']
          : destination + 1

      if (pageNumber) {
        if (
          n.pdfViewer.contentProvider.options.pageSize ==
            PAGE_SIZE.DOUBLEINTERNAL &&
          pageNumber > 2
        ) {
          pageNumber = pageNumber * 2 - 1
        }
        if (pageNumber > n.pdfViewer.pageCount) {
          pageNumber = n.pdfViewer.pageCount
        }
        n.pdfViewer.gotoPage(pageNumber)
        if (n.pdfHistory) {
          n.pdfHistory.push({ dest, hash: goToHash, page: pageNumber })
        }
      } else {
        n.pdfDocument.getPageIndex(destination).then((idx) => {
          const pNum = idx + 1
          const cacheKey = destination.num + ' ' + destination.gen + ' R'
          n._pagesRefCache[cacheKey] = pNum
          navigate(destination)
        })
      }
    }

    let destinationPromise
    if (typeof dest === 'string') {
      goToHash = dest
      destinationPromise = this.pdfDocument.getDestination(dest)
    } else {
      destinationPromise = Promise.resolve(dest)
    }

    destinationPromise.then((destination) => {
      if (!(destination instanceof Array)) return
      navigate(destination[0])
    })
  }

  customNavigateTo(dest) {
    if (dest == '' || dest == null || dest == 'null') return
    let pageNum = null
    if (!isNaN(Math.round(dest))) {
      pageNum = dest
    } else if (typeof dest === 'string') {
      pageNum = parseInt(dest.replace('#', ''), 10)
      if (isNaN(pageNum)) {
        window.open(
          dest,
          this.pdfViewer.previewObject.options.linkTarget == LINK_TARGET.SELF
            ? '_self'
            : '_blank'
        )
        return
      }
    }
    if (pageNum != null) this.pdfViewer.gotoPage(pageNum)
  }

  getDestinationHash(dest) {
    if (typeof dest === 'string') {
      return this.getAnchorUrl('#' + escape(dest))
    }
    if (dest instanceof Array) {
      const pageRef = dest[0]
      const pageNumber =
        pageRef instanceof Object
          ? this._pagesRefCache[pageRef.num + ' ' + pageRef.gen + ' R']
          : pageRef + 1

      if (pageNumber) {
        let hash = this.getAnchorUrl('#page=' + pageNumber)
        const zoom = dest[1]
        if (typeof zoom === 'object' && 'name' in zoom && zoom.name === 'XYZ') {
          let scale = dest[4] || this.pdfViewer.currentScaleValue
          const scaleNum = parseFloat(scale)
          if (scaleNum) scale = scaleNum * 100
          hash += '&zoom=' + scale
          if (dest[2] || dest[3]) {
            hash += ',' + (dest[2] || 0) + ',' + (dest[3] || 0)
          }
        }
        return hash
      }
    }
    return this.getAnchorUrl('')
  }

  getCustomDestinationHash(dest) {
    return '#' + escape(dest)
  }

  getAnchorUrl(anchor) {
    return (this.baseUrl || '') + anchor
  }

  setHash(hash) {
    if (hash.indexOf('=') >= 0) {
      const params = this.parseQueryString(hash)
      if ('nameddest' in params) {
        if (this.pdfHistory) {
          this.pdfHistory.updateNextHashParam(params.nameddest)
        }
        this.navigateTo(params.nameddest)
        return
      }
      let pageNum, zoomArgs
      if ('page' in params) {
        pageNum = params.page | 0 || 1
      }
      if ('zoom' in params) {
        const zoomParams = params.zoom.split(',')
        const zoomType = zoomParams[0]
        const scaleNum = parseFloat(zoomType)
        if (zoomType.indexOf('Fit') === -1) {
          zoomArgs = [
            null,
            { name: 'XYZ' },
            zoomParams.length > 1 ? zoomParams[1] | 0 : null,
            zoomParams.length > 2 ? zoomParams[2] | 0 : null,
            scaleNum ? scaleNum / 100 : zoomType,
          ]
        } else {
          if (zoomType === 'Fit' || zoomType === 'FitB') {
            zoomArgs = [null, { name: zoomType }]
          } else if (['FitH', 'FitBH', 'FitV', 'FitBV'].includes(zoomType)) {
            zoomArgs = [
              null,
              { name: zoomType },
              zoomParams.length > 1 ? zoomParams[1] | 0 : null,
            ]
          } else if (zoomType === 'FitR') {
            if (zoomParams.length !== 5) {
              console.error(
                "PDFLinkService_setHash: Not enough parameters for 'FitR'."
              )
            } else {
              zoomArgs = [
                null,
                { name: zoomType },
                zoomParams[1] | 0,
                zoomParams[2] | 0,
                zoomParams[3] | 0,
                zoomParams[4] | 0,
              ]
            }
          } else {
            console.error(
              "PDFLinkService_setHash: '" +
                zoomType +
                "' is not a valid zoom value."
            )
          }
        }
      }
      if (zoomArgs) {
        this.pdfViewer.scrollPageIntoView(pageNum || this.page, zoomArgs)
      } else if (pageNum) {
        this.page = pageNum
      }
      if ('pagemode' in params) {
        const event = document.createEvent('CustomEvent')
        event.initCustomEvent('pagemode', true, true, { mode: params.pagemode })
        this.pdfViewer.container.dispatchEvent(event)
      }
    } else if (/^\d+$/.test(hash)) {
      this.page = hash
    } else {
      if (this.pdfHistory) {
        this.pdfHistory.updateNextHashParam(unescape(hash))
      }
      this.navigateTo(unescape(hash))
    }
  }

  executeNamedAction(action) {
    switch (action) {
      case 'GoBack':
        if (this.pdfHistory) this.pdfHistory.back()
        break
      case 'GoForward':
        if (this.pdfHistory) this.pdfHistory.forward()
        break
      case 'NextPage':
        this.page++
        break
      case 'PrevPage':
        this.page--
        break
      case 'LastPage':
        this.page = this.pagesCount
        break
      case 'FirstPage':
        this.page = 1
        break
    }
    const event = document.createEvent('CustomEvent')
    event.initCustomEvent('namedaction', true, true, { action })
    this.pdfViewer.container.dispatchEvent(event)
  }

  cachePageRef(pageNum, pageRef) {
    const key = pageRef.num + ' ' + pageRef.gen + ' R'
    this._pagesRefCache[key] = pageNum
  }

  parseQueryString(query) {
    const parts = query.split('&')
    const params = Object.create(null)
    for (let i = 0, ii = parts.length; i < ii; ++i) {
      const param = parts[i].split('=')
      const key = param[0].toLowerCase()
      const value = param.length > 1 ? param[1] : null
      params[key] = value
    }
    return params
  }
}
