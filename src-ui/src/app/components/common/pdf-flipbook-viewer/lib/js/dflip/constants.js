/**
 * DFlip Constants and Defaults
 */

export const VERSION = '1.7.3.5'

export const PAGE_MODE = {
  SINGLE: 1,
  DOUBLE: 2,
  AUTO: null,
}

export const SINGLE_PAGE_MODE = {
  ZOOM: 1,
  BOOKLET: 2,
  AUTO: null,
}

export const CONTROLSPOSITION = {
  TOP: 'top',
  BOTTOM: 'bottom',
}

export const DIRECTION = {
  LTR: 1,
  RTL: 2,
}

export const LINK_TARGET = {
  SELF: 1,
  BLANK: 2,
}

export const SOURCE_TYPE = {
  IMAGE: 'image',
  PDF: 'pdf',
}

export const PAGE_SIZE = {
  AUTO: 0,
  SINGLE: 1,
  DOUBLEINTERNAL: 2,
}

export const DEFAULTS = {
  webgl: true,
  webglShadow: true,
  height: 'auto',
  enableDownload: true,
  duration: 800,
  direction: DIRECTION.LTR,
  pageMode: PAGE_MODE.AUTO,
  singlePageMode: SINGLE_PAGE_MODE.AUTO,
  backgroundColor: '#fff',
  forceFit: true,
  transparent: false,
  hard: 'none',
  openPage: 1,
  annotationClass: '',
  maxTextureSize: 1600,
  minTextureSize: 256,
  rangeChunkSize: 524288,
  icons: {
    next: 'df-icon-chevron-right',
    prev: 'df-icon-chevron-left',
    end: 'df-icon-chevron-double-right',
    start: 'df-icon-chevron-double-left',
    more: 'df-icon-three-dots',
    download: 'df-icon-download',
    print: 'df-icon-printer',
    zoomin: 'df-icon-zoom-in',
    zoomout: 'df-icon-zoom-out',
    fullscreen: 'df-icon-fullscreen',
    fitscreen: 'df-icon-arrows-angle-expand',
    doublepage: 'df-icon-book',
    singlepage: 'df-icon-file-earmark',
  },
  text: {
    previousPage: 'Previous Page',
    nextPage: 'Next Page',
    toggleFullscreen: 'Toggle Fullscreen',
    zoomIn: 'Zoom In',
    zoomOut: 'Zoom Out',
    singlePageMode: 'Single Page Mode',
    doublePageMode: 'Double Page Mode',
    downloadPDFFile: 'Download PDF File',
    printPDFFile: 'Print PDF File',
    gotoFirstPage: 'Goto First Page',
    gotoLastPage: 'Goto Last Page',
  },
  allControls:
    'altPrev,pageNumber,altNext,zoomIn,zoomOut,fullScreen,download,print,more,pageMode,startPage,endPage',
  moreControls: 'download,pageMode,startPage,endPage',
  hideControls: '',
  controlsPosition: CONTROLSPOSITION.BOTTOM,
  paddingTop: 30,
  paddingLeft: 20,
  paddingRight: 20,
  paddingBottom: 30,
  scrollWheel: true,
  onCreate: function (e) {},
  onCreateUI: function (e) {},
  onFlip: function (e) {},
  beforeFlip: function (e) {},
  onReady: function (e) {},
  zoomRatio: 1.5,
  pageSize: PAGE_SIZE.AUTO,
  pdfjsSrc: 'js/libs/pdf.min.js',
  pdfjsWorkerSrc: 'js/libs/pdf.worker.min.js',
  imageResourcesPath: 'images/pdfjs/',
  cMapUrl: 'cmaps/',
  enableDebugLog: false,
  canvasToBlob: false,
  enableAnnotation: true,
  pdfRenderQuality: 0.9,
  textureLoadFallback: 'blank',
  stiffness: 3,
  backgroundImage: '',
  pageRatio: null,
  spotLightIntensity: 0.22,
  ambientLightColor: '#fff',
  ambientLightIntensity: 0.8,
  shadowOpacity: 0.15,
  linkTarget: LINK_TARGET.BLANK,
}
