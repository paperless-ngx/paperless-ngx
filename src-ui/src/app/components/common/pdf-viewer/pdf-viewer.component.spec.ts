import { SimpleChange } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import * as pdfjs from 'pdfjs-dist/legacy/build/pdf.mjs'
import { PDFSinglePageViewer, PDFViewer } from 'pdfjs-dist/web/pdf_viewer.mjs'
import { PngxPdfViewerComponent } from './pdf-viewer.component'
import { PdfRenderMode, PdfZoomLevel, PdfZoomScale } from './pdf-viewer.types'

describe('PngxPdfViewerComponent', () => {
  let fixture: ComponentFixture<PngxPdfViewerComponent>
  let component: PngxPdfViewerComponent

  const initComponent = async (src = 'test.pdf') => {
    component.src = src
    fixture.detectChanges()
    await fixture.whenStable()
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PngxPdfViewerComponent],
    }).compileComponents()

    fixture = TestBed.createComponent(PngxPdfViewerComponent)
    component = fixture.componentInstance
  })

  it('loads a document and emits events', async () => {
    const loadSpy = jest.fn()
    const renderedSpy = jest.fn()
    component.afterLoadComplete.subscribe(loadSpy)
    component.rendered.subscribe(renderedSpy)

    await initComponent()

    expect(pdfjs.GlobalWorkerOptions.workerSrc).toBe(
      '/assets/js/pdf.worker.min.mjs'
    )
    const isVisible = (component as any).findController.onIsPageVisible as
      | (() => boolean)
      | undefined
    expect(isVisible?.()).toBe(true)
    expect(loadSpy).toHaveBeenCalledWith(
      expect.objectContaining({ numPages: 1 })
    )
    expect(renderedSpy).toHaveBeenCalled()
    expect((component as any).pdfViewer).toBeInstanceOf(PDFViewer)
  })

  it('initializes single-page viewer and disables text layer', async () => {
    component.renderMode = PdfRenderMode.Single
    component.selectable = false

    await initComponent()

    const viewer = (component as any).pdfViewer as PDFSinglePageViewer & {
      options: Record<string, unknown>
    }
    expect(viewer).toBeInstanceOf(PDFSinglePageViewer)
    expect(viewer.options.textLayerMode).toBe(0)
  })

  it('applies zoom, rotation, and page changes', async () => {
    await initComponent()

    const pageSpy = jest.fn()
    component.pageChange.subscribe(pageSpy)

    // In real usage the viewer may have multiple pages; our pdfjs mock defaults
    // to a single page, so explicitly simulate a multi-page document here.
    const pdf = (component as any).pdf as { numPages: number }
    pdf.numPages = 3
    const viewer = (component as any).pdfViewer as PDFViewer
    viewer.setDocument(pdf)

    component.zoomScale = PdfZoomScale.PageFit
    component.zoom = PdfZoomLevel.Two
    component.rotation = 90
    component.page = 2

    component.ngOnChanges({
      zoomScale: new SimpleChange(
        PdfZoomScale.PageWidth,
        PdfZoomScale.PageFit,
        false
      ),
      zoom: new SimpleChange(PdfZoomLevel.One, PdfZoomLevel.Two, false),
      rotation: new SimpleChange(undefined, 90, false),
      page: new SimpleChange(undefined, 2, false),
    })

    expect(viewer.pagesRotation).toBe(90)
    expect(viewer.currentPageNumber).toBe(2)
    expect(pageSpy).toHaveBeenCalledWith(2)

    viewer.currentScale = 1
    ;(component as any).applyScale()
    expect(viewer.currentScaleValue).toBe(PdfZoomScale.PageFit)
    expect(viewer.currentScale).toBe(2)

    const applyScaleSpy = jest.spyOn(component as any, 'applyScale')
    component.page = 2
    ;(component as any).lastViewerPage = 2
    ;(component as any).applyViewerState()
    expect((component as any).lastViewerPage).toBeUndefined()
    expect(applyScaleSpy).toHaveBeenCalled()
  })

  it('dispatches find when search query changes after render', async () => {
    await initComponent()

    const eventBus = (component as any).eventBus as { dispatch: jest.Mock }
    const dispatchSpy = jest.spyOn(eventBus, 'dispatch')

    ;(component as any).hasRenderedPage = true
    component.searchQuery = 'needle'
    component.ngOnChanges({
      searchQuery: new SimpleChange('', 'needle', false),
    })

    expect(dispatchSpy).toHaveBeenCalledWith('find', {
      query: 'needle',
      caseSensitive: false,
      highlightAll: true,
      phraseSearch: true,
    })

    component.ngOnChanges({
      searchQuery: new SimpleChange('needle', 'needle', false),
    })
    expect(dispatchSpy).toHaveBeenCalledTimes(1)
  })

  it('emits error when document load fails', async () => {
    const errorSpy = jest.fn()
    component.loadError.subscribe(errorSpy)

    jest.spyOn(pdfjs, 'getDocument').mockImplementationOnce(() => {
      return {
        promise: Promise.reject(new Error('boom')),
        destroy: jest.fn(),
      } as any
    })

    await initComponent('bad.pdf')

    expect(errorSpy).toHaveBeenCalled()
  })

  it('cleans up resources on destroy', async () => {
    await initComponent()

    const viewer = (component as any).pdfViewer as { cleanup: jest.Mock }
    const loadingTask = (component as any).loadingTask as unknown as {
      destroy: jest.Mock
    }
    const resizeObserver = (component as any).resizeObserver as unknown as {
      disconnect: jest.Mock
    }
    const eventBus = (component as any).eventBus as { off: jest.Mock }

    jest.spyOn(viewer, 'cleanup')
    jest.spyOn(loadingTask, 'destroy')
    jest.spyOn(resizeObserver, 'disconnect')
    jest.spyOn(eventBus, 'off')

    component.ngOnDestroy()

    expect(eventBus.off).toHaveBeenCalledWith(
      'pagerendered',
      expect.any(Function)
    )
    expect(eventBus.off).toHaveBeenCalledWith('pagesinit', expect.any(Function))
    expect(eventBus.off).toHaveBeenCalledWith(
      'pagechanging',
      expect.any(Function)
    )
    expect(resizeObserver.disconnect).toHaveBeenCalled()
    expect(loadingTask.destroy).toHaveBeenCalled()
    expect(viewer.cleanup).toHaveBeenCalled()
    expect((component as any).pdfViewer).toBeUndefined()
  })

  it('skips work when viewer is missing or has no pages', () => {
    const eventBus = (component as any).eventBus as { dispatch: jest.Mock }
    const dispatchSpy = jest.spyOn(eventBus, 'dispatch')
    ;(component as any).dispatchFindIfReady()
    expect(dispatchSpy).not.toHaveBeenCalled()
    ;(component as any).applyViewerState()
    ;(component as any).applyScale()

    const viewer = new PDFViewer({ eventBus: undefined })
    viewer.pagesCount = 0
    ;(component as any).pdfViewer = viewer
    viewer.currentScale = 5
    ;(component as any).applyScale()
    expect(viewer.currentScale).toBe(5)
  })

  it('returns early on src change in ngOnChanges', () => {
    const loadSpy = jest.spyOn(component as any, 'loadDocument')
    const initSpy = jest.spyOn(component as any, 'initViewer')
    const scaleSpy = jest.spyOn(component as any, 'applyViewerState')
    const resizeSpy = jest.spyOn(component as any, 'setupResizeObserver')

    // Angular sets the input value before calling ngOnChanges; mirror that here.
    component.src = 'test.pdf'
    component.ngOnChanges({
      src: new SimpleChange(undefined, 'test.pdf', true),
      zoomScale: new SimpleChange(
        PdfZoomScale.PageWidth,
        PdfZoomScale.PageFit,
        false
      ),
    })

    expect(loadSpy).toHaveBeenCalled()
    expect(resizeSpy).not.toHaveBeenCalled()
    expect(initSpy).not.toHaveBeenCalled()
    expect(scaleSpy).not.toHaveBeenCalled()
  })

  it('resets viewer state on src change', () => {
    const mockViewer = {
      setDocument: jest.fn(),
      currentPageNumber: 7,
      cleanup: jest.fn(),
    }
    ;(component as any).pdfViewer = mockViewer
    ;(component as any).loadingTask = { destroy: jest.fn() }
    jest.spyOn(component as any, 'loadDocument').mockImplementation(() => {})

    component.src = 'test.pdf'
    component.ngOnChanges({
      src: new SimpleChange(undefined, 'test.pdf', true),
    })

    expect(mockViewer.setDocument).toHaveBeenCalledWith(null)
    expect(mockViewer.currentPageNumber).toBe(1)
  })

  it('applies viewer state after view init when already loaded', () => {
    const applySpy = jest.spyOn(component as any, 'applyViewerState')
    ;(component as any).hasLoaded = true
    ;(component as any).pdf = { numPages: 1 }

    fixture.detectChanges()

    expect(applySpy).toHaveBeenCalled()
  })

  it('skips viewer state after view init when no pdf is available', () => {
    const applySpy = jest.spyOn(component as any, 'applyViewerState')
    ;(component as any).hasLoaded = true

    fixture.detectChanges()

    expect(applySpy).not.toHaveBeenCalled()
  })

  it('does not reload when already loaded', async () => {
    await initComponent()

    const getDocumentSpy = jest.spyOn(pdfjs, 'getDocument')
    const callCount = getDocumentSpy.mock.calls.length
    await (component as any).loadDocument()

    expect(getDocumentSpy).toHaveBeenCalledTimes(callCount)
  })

  it('runs applyScale on resize observer notifications', async () => {
    await initComponent()

    const applySpy = jest.spyOn(component as any, 'applyScale')
    const resizeObserver = (component as any).resizeObserver as {
      trigger: () => void
    }
    resizeObserver.trigger()

    expect(applySpy).toHaveBeenCalled()
  })

  it('skips page work when no pages are available', async () => {
    await initComponent()

    const viewer = (component as any).pdfViewer as PDFViewer
    viewer.pagesCount = 0
    const applyScaleSpy = jest.spyOn(component as any, 'applyScale')

    component.page = undefined
    ;(component as any).lastViewerPage = 1
    ;(component as any).applyViewerState()

    expect(applyScaleSpy).not.toHaveBeenCalled()
    expect((component as any).lastViewerPage).toBe(1)
  })

  it('falls back to a default zoom when input is invalid', async () => {
    await initComponent()

    const viewer = (component as any).pdfViewer as PDFViewer
    viewer.currentScale = 3
    component.zoom = 'not-a-number' as PdfZoomLevel
    ;(component as any).applyScale()

    expect(viewer.currentScale).toBe(3)
  })

  it('re-initializes viewer on selectable or render mode changes', async () => {
    await initComponent()

    const initSpy = jest.spyOn(component as any, 'initViewer')
    component.selectable = false
    component.renderMode = PdfRenderMode.Single

    component.ngOnChanges({
      selectable: new SimpleChange(true, false, false),
      renderMode: new SimpleChange(
        PdfRenderMode.All,
        PdfRenderMode.Single,
        false
      ),
    })

    expect(initSpy).toHaveBeenCalled()
  })
})
