export class PDFDocumentProxy {
  numPages = 1
}

export class PDFDocumentLoadingTask {
  promise: Promise<PDFDocumentProxy>
  destroyed = false

  constructor(doc: PDFDocumentProxy) {
    this.promise = Promise.resolve(doc)
  }

  destroy(): void {
    this.destroyed = true
  }
}

export const GlobalWorkerOptions = {
  workerSrc: '',
}

export const getDocument = (_src: unknown): PDFDocumentLoadingTask => {
  return new PDFDocumentLoadingTask(new PDFDocumentProxy())
}
