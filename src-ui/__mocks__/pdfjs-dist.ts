export const getDocument = jest.fn(() => ({
  promise: Promise.resolve({ numPages: 3 }),
}))

export const GlobalWorkerOptions = { workerSrc: '' }
export const VerbosityLevel = { ERRORS: 0 }

globalThis.pdfjsLib = {
  getDocument,
  GlobalWorkerOptions,
  VerbosityLevel,
  AbortException: class AbortException extends Error {},
}
