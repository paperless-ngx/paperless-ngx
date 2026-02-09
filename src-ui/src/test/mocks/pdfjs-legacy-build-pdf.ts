export class PDFDocumentProxy {
  numPages = 1
}

export class PDFDocumentLoadingTask {
  promise: Promise<PDFDocumentProxy>
  destroyed = false

  constructor(promise: Promise<PDFDocumentProxy>) {
    this.promise = promise
  }

  destroy(): void {
    this.destroyed = true
  }
}

export const GlobalWorkerOptions = {
  workerSrc: '',
}

export const getDocument = (_src: unknown): PDFDocumentLoadingTask => {
  return new PDFDocumentLoadingTask(Promise.resolve(new PDFDocumentProxy()))
}
