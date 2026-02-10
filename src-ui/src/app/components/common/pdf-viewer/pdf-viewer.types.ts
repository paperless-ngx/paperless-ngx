export type PngxPdfDocumentProxy = {
  numPages: number
}

export type PdfSource = string | { url: string; password?: string }

export enum PdfRenderMode {
  Single = 'single',
  All = 'all',
}

export enum PdfZoomScale {
  PageFit = 'page-fit',
  PageWidth = 'page-width',
}

export enum PdfZoomLevel {
  Quarter = '.25',
  Half = '.5',
  ThreeQuarters = '.75',
  One = '1',
  OneAndHalf = '1.5',
  Two = '2',
  Three = '3',
}
