/**
 * This file is taken and modified from https://github.com/VadimDez/ng2-pdf-viewer/blob/10.0.0/src/app/pdf-viewer/utils/event-bus-utils.ts
 * Created by vadimdez on 21/06/16.
 */
import { fromEvent, Subject } from 'rxjs'
import { takeUntil } from 'rxjs/operators'

import type { EventBus } from 'pdfjs-dist/web/pdf_viewer'

// interface EventBus {
//   on(eventName: string, listener: Function): void;
//   off(eventName: string, listener: Function): void;
//   _listeners: any;
//   dispatch(eventName: string, data: Object): void;
//   _on(eventName: any, listener: any, options?: null): void;
//   _off(eventName: any, listener: any, options?: null): void;
// }

export function createEventBus(pdfJsViewer: any, destroy$: Subject<void>) {
  const globalEventBus: EventBus = new pdfJsViewer.EventBus()
  attachDOMEventsToEventBus(globalEventBus, destroy$)
  return globalEventBus
}

function attachDOMEventsToEventBus(
  eventBus: EventBus,
  destroy$: Subject<void>
): void {
  fromEvent(eventBus, 'documentload')
    .pipe(takeUntil(destroy$))
    .subscribe(() => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('documentload', true, true, {})
      window.dispatchEvent(event)
    })

  fromEvent(eventBus, 'pagerendered')
    .pipe(takeUntil(destroy$))
    .subscribe(({ pageNumber, cssTransform, source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('pagerendered', true, true, {
        pageNumber,
        cssTransform,
      })
      source.div.dispatchEvent(event)
    })

  fromEvent(eventBus, 'textlayerrendered')
    .pipe(takeUntil(destroy$))
    .subscribe(({ pageNumber, source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('textlayerrendered', true, true, { pageNumber })
      source.textLayerDiv?.dispatchEvent(event)
    })

  fromEvent(eventBus, 'pagechanging')
    .pipe(takeUntil(destroy$))
    .subscribe(({ pageNumber, source }: any) => {
      const event = document.createEvent('UIEvents') as any
      event.initEvent('pagechanging', true, true)
      /* tslint:disable:no-string-literal */
      event['pageNumber'] = pageNumber
      source.container.dispatchEvent(event)
    })

  fromEvent(eventBus, 'pagesinit')
    .pipe(takeUntil(destroy$))
    .subscribe(({ source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('pagesinit', true, true, null)
      source.container.dispatchEvent(event)
    })

  fromEvent(eventBus, 'pagesloaded')
    .pipe(takeUntil(destroy$))
    .subscribe(({ pagesCount, source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('pagesloaded', true, true, { pagesCount })
      source.container.dispatchEvent(event)
    })

  fromEvent(eventBus, 'scalechange')
    .pipe(takeUntil(destroy$))
    .subscribe(({ scale, presetValue, source }: any) => {
      const event = document.createEvent('UIEvents') as any
      event.initEvent('scalechange', true, true)
      /* tslint:disable:no-string-literal */
      event['scale'] = scale
      /* tslint:disable:no-string-literal */
      event['presetValue'] = presetValue
      source.container.dispatchEvent(event)
    })

  fromEvent(eventBus, 'updateviewarea')
    .pipe(takeUntil(destroy$))
    .subscribe(({ location, source }: any) => {
      const event = document.createEvent('UIEvents') as any
      event.initEvent('updateviewarea', true, true)
      event['location'] = location
      source.container.dispatchEvent(event)
    })

  fromEvent(eventBus, 'find')
    .pipe(takeUntil(destroy$))
    .subscribe(
      ({
        source,
        type,
        query,
        phraseSearch,
        caseSensitive,
        highlightAll,
        findPrevious,
      }: any) => {
        if (source === window) {
          return // event comes from FirefoxCom, no need to replicate
        }
        const event = document.createEvent('CustomEvent')
        event.initCustomEvent('find' + type, true, true, {
          query,
          phraseSearch,
          caseSensitive,
          highlightAll,
          findPrevious,
        })
        window.dispatchEvent(event)
      }
    )

  fromEvent(eventBus, 'attachmentsloaded')
    .pipe(takeUntil(destroy$))
    .subscribe(({ attachmentsCount, source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('attachmentsloaded', true, true, {
        attachmentsCount,
      })
      source.container.dispatchEvent(event)
    })

  fromEvent(eventBus, 'sidebarviewchanged')
    .pipe(takeUntil(destroy$))
    .subscribe(({ view, source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('sidebarviewchanged', true, true, { view })
      source.outerContainer.dispatchEvent(event)
    })

  fromEvent(eventBus, 'pagemode')
    .pipe(takeUntil(destroy$))
    .subscribe(({ mode, source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('pagemode', true, true, { mode })
      source.pdfViewer.container.dispatchEvent(event)
    })

  fromEvent(eventBus, 'namedaction')
    .pipe(takeUntil(destroy$))
    .subscribe(({ action, source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('namedaction', true, true, { action })
      source.pdfViewer.container.dispatchEvent(event)
    })

  fromEvent(eventBus, 'presentationmodechanged')
    .pipe(takeUntil(destroy$))
    .subscribe(({ active, switchInProgress }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('presentationmodechanged', true, true, {
        active,
        switchInProgress,
      })
      window.dispatchEvent(event)
    })

  fromEvent(eventBus, 'outlineloaded')
    .pipe(takeUntil(destroy$))
    .subscribe(({ outlineCount, source }: any) => {
      const event = document.createEvent('CustomEvent')
      event.initCustomEvent('outlineloaded', true, true, { outlineCount })
      source.container.dispatchEvent(event)
    })
}
