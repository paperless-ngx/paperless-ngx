import '@angular/localize/init'
import { jest } from '@jest/globals'
import { setupZoneTestEnv } from 'jest-preset-angular/setup-env/zone'
import { TextDecoder, TextEncoder } from 'node:util'
if (process.env.NODE_ENV === 'test') {
  setupZoneTestEnv()
}
;(globalThis as any).TextEncoder = TextEncoder as unknown as {
  new (): TextEncoder
}
;(globalThis as any).TextDecoder = TextDecoder as unknown as {
  new (): TextDecoder
}

import { registerLocaleData } from '@angular/common'
import localeAf from '@angular/common/locales/af'
import localeAr from '@angular/common/locales/ar'
import localeBe from '@angular/common/locales/be'
import localeBg from '@angular/common/locales/bg'
import localeCa from '@angular/common/locales/ca'
import localeCs from '@angular/common/locales/cs'
import localeDa from '@angular/common/locales/da'
import localeDe from '@angular/common/locales/de'
import localeEl from '@angular/common/locales/el'
import localeEnGb from '@angular/common/locales/en-GB'
import localeEs from '@angular/common/locales/es'
import localeFa from '@angular/common/locales/fa'
import localeFi from '@angular/common/locales/fi'
import localeFr from '@angular/common/locales/fr'
import localeHu from '@angular/common/locales/hu'
import localeId from '@angular/common/locales/id'
import localeIt from '@angular/common/locales/it'
import localeJa from '@angular/common/locales/ja'
import localeKo from '@angular/common/locales/ko'
import localeLb from '@angular/common/locales/lb'
import localeNl from '@angular/common/locales/nl'
import localeNo from '@angular/common/locales/no'
import localePl from '@angular/common/locales/pl'
import localePt from '@angular/common/locales/pt'
import localeRo from '@angular/common/locales/ro'
import localeRu from '@angular/common/locales/ru'
import localeSk from '@angular/common/locales/sk'
import localeSl from '@angular/common/locales/sl'
import localeSr from '@angular/common/locales/sr'
import localeSv from '@angular/common/locales/sv'
import localeTr from '@angular/common/locales/tr'
import localeUk from '@angular/common/locales/uk'
import localeVi from '@angular/common/locales/vi'
import localeZh from '@angular/common/locales/zh'
import localeZhHant from '@angular/common/locales/zh-Hant'

registerLocaleData(localeAf)
registerLocaleData(localeAr)
registerLocaleData(localeBe)
registerLocaleData(localeBg)
registerLocaleData(localeCa)
registerLocaleData(localeCs)
registerLocaleData(localeDa)
registerLocaleData(localeDe)
registerLocaleData(localeEl)
registerLocaleData(localeEnGb)
registerLocaleData(localeEs)
registerLocaleData(localeFa)
registerLocaleData(localeFi)
registerLocaleData(localeFr)
registerLocaleData(localeHu)
registerLocaleData(localeId)
registerLocaleData(localeIt)
registerLocaleData(localeJa)
registerLocaleData(localeKo)
registerLocaleData(localeLb)
registerLocaleData(localeNl)
registerLocaleData(localeNo)
registerLocaleData(localePl)
registerLocaleData(localePt, 'pt-BR')
registerLocaleData(localePt, 'pt-PT')
registerLocaleData(localeRo)
registerLocaleData(localeRu)
registerLocaleData(localeSk)
registerLocaleData(localeSl)
registerLocaleData(localeSr)
registerLocaleData(localeSv)
registerLocaleData(localeTr)
registerLocaleData(localeUk)
registerLocaleData(localeVi)
registerLocaleData(localeZh)
registerLocaleData(localeZhHant)

/* global mocks for jsdom */
const mock = () => {
  let storage: { [key: string]: string } = {}
  return {
    getItem: (key: string) => (key in storage ? storage[key] : null),
    setItem: (key: string, value: string) => {
      if (value.length > 1000000) throw new Error('localStorage overflow')
      storage[key] = value || ''
    },
    removeItem: (key: string) => delete storage[key],
    clear: () => (storage = {}),
  }
}

Object.defineProperty(globalThis, 'open', { value: jest.fn() })
Object.defineProperty(globalThis, 'localStorage', { value: mock() })
Object.defineProperty(globalThis, 'sessionStorage', { value: mock() })
Object.defineProperty(globalThis, 'getComputedStyle', {
  value: () => ['-webkit-appearance'],
})
Object.defineProperty(navigator, 'clipboard', {
  value: {
    writeText: async () => {},
  },
})
Object.defineProperty(navigator, 'canShare', { value: () => true })
if (!navigator.share) {
  Object.defineProperty(navigator, 'share', { value: jest.fn() })
}
if (!globalThis.URL.createObjectURL) {
  Object.defineProperty(globalThis.URL, 'createObjectURL', { value: jest.fn() })
}
if (!globalThis.URL.revokeObjectURL) {
  Object.defineProperty(globalThis.URL, 'revokeObjectURL', { value: jest.fn() })
}
class MockResizeObserver {
  private readonly callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }

  observe = jest.fn()
  unobserve = jest.fn()
  disconnect = jest.fn()

  trigger = (entries: ResizeObserverEntry[] = []) => {
    this.callback(entries, this)
  }
}

Object.defineProperty(globalThis, 'ResizeObserver', {
  writable: true,
  configurable: true,
  value: MockResizeObserver,
})

if (typeof IntersectionObserver === 'undefined') {
  class MockIntersectionObserver {
    constructor(
      public callback: IntersectionObserverCallback,
      public options?: IntersectionObserverInit
    ) {}

    observe = jest.fn()
    unobserve = jest.fn()
    disconnect = jest.fn()
    takeRecords = jest.fn()
  }

  Object.defineProperty(globalThis, 'IntersectionObserver', {
    writable: true,
    configurable: true,
    value: MockIntersectionObserver,
  })
}

HTMLCanvasElement.prototype.getContext = <
  typeof HTMLCanvasElement.prototype.getContext
>jest.fn()

if (!HTMLElement.prototype.scrollTo) {
  HTMLElement.prototype.scrollTo = jest.fn()
}

jest.mock('uuid', () => ({
  v4: jest.fn(() =>
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char: string) => {
      const random = Math.floor(Math.random() * 16)
      const value = char === 'x' ? random : (random & 0x3) | 0x8
      return value.toString(16)
    })
  ),
}))

jest.mock('pdfjs-dist')
