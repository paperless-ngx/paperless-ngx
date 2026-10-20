import { ElementRef } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { of, Subject, throwError } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { Document } from 'src/app/data/document'
import {
  OcrTemplate,
  OcrTemplateZone,
  OcrZoneTestResult,
} from 'src/app/data/ocr-template'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { ToastService } from 'src/app/services/toast.service'
import { OcrTemplateEditorComponent } from './ocr-template-editor.component'

function zone(): OcrTemplateZone {
  return {
    name: 'Invoice number',
    custom_field: 1,
    x: 100,
    y: 100,
    width: 200,
    height: 100,
    page: 1,
    ocr_language: 'eng',
    transform: 'strip',
    validation_regex: '',
    order: 0,
  }
}

describe('OcrTemplateEditorComponent', () => {
  let fixture: ComponentFixture<OcrTemplateEditorComponent>
  let component: OcrTemplateEditorComponent
  const documents = {
    list: jest.fn(),
    get: jest.fn(),
  }
  const templates = {
    testZone: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    getPageImageUrl: (id: number, page: number) => `/preview/${id}/${page}`,
  }
  const modal = { open: jest.fn() }
  const activeModal = { close: jest.fn(), dismiss: jest.fn() }

  beforeEach(async () => {
    documents.list.mockReset().mockReturnValue(of({ results: [] }))
    documents.get.mockReset().mockReturnValue(of({ id: 1, page_count: 3 }))
    templates.testZone.mockReset()
    templates.create.mockReset()
    templates.update.mockReset()
    activeModal.close.mockReset()
    await TestBed.configureTestingModule({
      imports: [OcrTemplateEditorComponent],
      providers: [
        { provide: NgbActiveModal, useValue: activeModal },
        { provide: DocumentService, useValue: documents },
        { provide: OcrTemplateService, useValue: templates },
        ...[CustomFieldsService, DocumentTypeService, CorrespondentService].map(
          (provide) => ({
            provide,
            useValue: {
              listAll: () => of({ results: [] }),
              clearCache: jest.fn(),
            },
          })
        ),
        { provide: NgbModal, useValue: modal },
        {
          provide: ToastService,
          useValue: {
            showInfo: jest.fn(),
            showSuccess: jest.fn(),
            showError: jest.fn(),
          },
        },
      ],
    })
      .overrideComponent(OcrTemplateEditorComponent, {
        set: { template: '{{ searchStatus() }}', imports: [] },
      })
      .compileComponents()
    fixture = TestBed.createComponent(OcrTemplateEditorComponent)
    component = fixture.componentInstance
  })

  afterEach(() => jest.useRealTimers())

  function prepareOverlay() {
    const image = document.createElement('img')
    Object.defineProperties(image, {
      naturalWidth: { value: 1000 },
      naturalHeight: { value: 1000 },
      clientWidth: { value: 1000 },
    })
    const overlay = document.createElementNS(
      'http://www.w3.org/2000/svg',
      'svg'
    )
    Object.assign(overlay, {
      getScreenCTM: () => ({ inverse: () => ({}) }),
      createSVGPoint: () => ({
        x: 0,
        y: 0,
        matrixTransform() {
          return { x: this.x, y: this.y }
        },
      }),
      setPointerCapture: jest.fn(),
      hasPointerCapture: () => true,
      releasePointerCapture: jest.fn(),
    })
    component.imageRef = new ElementRef(image)
    component.overlayRef = new ElementRef(overlay)
    component.previewStatus = 'ready'
  }

  function pointer(x: number, y: number, pointerId = 1): PointerEvent {
    return Object.assign(
      new MouseEvent('pointermove', { clientX: x, clientY: y, button: 0 }),
      { pointerId }
    ) as PointerEvent
  }

  it('edits a copy of the supplied template and restores its sample document', () => {
    const original: OcrTemplate = {
      ...component.template,
      id: 3,
      name: 'Invoices',
      sample_document: 5,
      zones: [zone()],
      combine_formats: { '1': '{Invoice number}' },
    }
    component.object = original
    fixture.detectChanges()

    expect(component.isNew).toBe(false)
    expect(component.previewDocId).toBe(5)
    expect(component.pageImageUrl).toBe('/preview/5/0')
    expect(component.isDirty).toBe(false)
    component.template.name = 'Edited'
    component.template.zones[0].x = 500
    component.template.combine_formats['1'] = 'Edited format'
    expect(original.name).toBe('Invoices')
    expect(original.zones[0].x).toBe(100)
    expect(original.combine_formats['1']).toBe('{Invoice number}')
  })

  it('updates an existing template, notifies the list, and closes the dialog', () => {
    component.object = { ...component.template, id: 3, name: 'Invoices' }
    fixture.detectChanges()
    component.template.name = 'Renamed'
    const saved = { ...component.template }
    templates.update.mockReturnValue(of(saved))
    const succeeded = jest.spyOn(component.succeeded, 'emit')

    component.save()

    expect(templates.update).toHaveBeenCalledWith(component.template)
    expect(templates.create).not.toHaveBeenCalled()
    expect(succeeded).toHaveBeenCalledWith(saved)
    expect(activeModal.close).toHaveBeenCalledWith(saved)
  })

  it('searches across document metadata even when a template document type is set', () => {
    jest.useFakeTimers()
    const term$ = new Subject<string>()
    const doc = { id: 1, title: 'Electricity Bill' } as Document
    documents.list.mockReturnValue(of({ results: [doc] }))
    component.template.document_type = 2
    const found = jest.fn()
    component.searchDocuments(term$).subscribe(found)

    term$.next(' northw ')
    jest.advanceTimersByTime(250)

    expect(documents.list).toHaveBeenCalledWith(1, 10, 'created', true, {
      search: 'northw',
      truncate_content: true,
    })
    expect(found).toHaveBeenCalledWith([doc])
    expect(component.searchStatus()).toBe('ready')
  })

  it('distinguishes an empty search from a failed request and allows another search', () => {
    jest.useFakeTimers()
    const term$ = new Subject<string>()
    component.searchDocuments(term$).subscribe()
    term$.next('missing')
    jest.advanceTimersByTime(250)
    expect(component.searchStatus()).toBe('empty')

    documents.list.mockReturnValueOnce(throwError(() => new Error('offline')))
    term$.next('offline')
    jest.advanceTimersByTime(250)
    expect(component.searchStatus()).toBe('error')

    term$.next('retry')
    jest.advanceTimersByTime(250)
    expect(component.searchStatus()).toBe('empty')
  })

  it('renders asynchronous search feedback without a user interaction', async () => {
    fixture.detectChanges()
    const pending = new Subject<{ results: Document[] }>()
    const term$ = new Subject<string>()
    documents.list.mockReturnValue(pending)
    component.searchDocuments(term$).subscribe()
    term$.next('missing')
    await new Promise((resolve) => setTimeout(resolve, 275))
    pending.next({ results: [] })
    await fixture.whenStable()

    expect(fixture.nativeElement.textContent).toBe('empty')
  })

  it('clears the selection on a click in empty space without adding a zone', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    component.selectZone(0)
    component.onOverlayPointerDown(pointer(600, 600))
    component.onOverlayPointerUp(pointer(602, 601))

    expect(component.template.zones.length).toBe(1)
    expect(component.selectedZoneIndex).toBeNull()
  })

  it('moves a zone when dragging on it instead of drawing', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    component.onOverlayPointerDown(pointer(150, 150))
    component.onOverlayPointerUp(pointer(250, 200))

    expect(component.template.zones.length).toBe(1)
    expect(component.template.zones[0]).toMatchObject({ x: 200, y: 150 })
    expect(component.selectedZoneIndex).toBe(0)
  })

  it('draws in empty space within the page bounds, using the release position', () => {
    prepareOverlay()
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerUp(pointer(1200, 250))

    expect(component.template.zones[0]).toMatchObject({
      x: 100,
      y: 100,
      width: 900,
      height: 150,
      custom_field: null,
    })
    expect(component.selectedZoneIndex).toBe(0)
  })

  it('discards a drawing on Escape and ignores other pointers', () => {
    prepareOverlay()
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerUp(pointer(300, 200, 2))
    expect(component.drawingRect()).not.toBeNull()

    component.cancelDrawing()
    component.onOverlayPointerUp(pointer(300, 200))
    expect(component.template.zones).toEqual([])
  })

  it('opens the zone in the Zones tab and returns to the list', () => {
    component.template.zones = [zone(), zone()]
    component.activeTab = 'settings'

    component.selectZone(1)
    expect(component.activeTab).toBe('zones')
    expect(component.selectedZone).toBe(component.template.zones[1])

    component.deselectZone()
    expect(component.selectedZone).toBeNull()
    expect(component.activeTab).toBe('zones')

    component.selectZone(0)
    component.deleteSelectedZone()
    expect(component.template.zones.length).toBe(1)
    expect(component.selectedZone).toBeNull()
  })

  it('creates a custom field in the dialog and assigns it to the zone', () => {
    const succeeded = new Subject<CustomField>()
    const dialog = {
      dialogMode: { set: jest.fn() },
      object: null,
      succeeded,
      failed: new Subject(),
    }
    modal.open.mockReturnValue({ componentInstance: dialog })
    const created = {
      id: 5,
      name: 'Total',
      data_type: CustomFieldDataType.Monetary,
    }
    TestBed.inject(CustomFieldsService).listAll = () =>
      of({
        count: 2,
        all: [5, 6],
        results: [
          created,
          { id: 6, name: 'Status', data_type: CustomFieldDataType.Select },
        ],
      })
    component.template.zones = [zone()]
    component.selectZone(0)

    component.createField()
    expect(dialog.object).toEqual({ name: 'Invoice number' })
    succeeded.next(created)

    expect(component.template.zones[0]).toMatchObject({
      target: 'custom_field',
      custom_field: 5,
    })
    expect(component.fieldItems().map((item) => item.id)).toEqual([
      'title',
      'asn',
      'created',
      5,
    ])
  })

  it('builds a combine format for zones sharing a field and prunes stale ones', () => {
    const first = { ...zone(), name: 'First' }
    const second = { ...zone(), name: 'Second' }
    const other = { ...zone(), name: 'Other', custom_field: 2 }
    component.template.zones = [first, second, other]
    component.template.combine_formats = { '2': '{Other}' }

    expect(component.isFieldShared(first)).toBe(true)
    expect(component.isFieldShared(other)).toBe(false)
    expect(component.defaultCombineFormat(first)).toBe('{First} {Second}')

    component.insertCombineToken(first, second)
    component.insertCombineToken(first, first)
    expect(component.getCombineFormat(second)).toBe('{Second} {First}')

    templates.create.mockReturnValue(of(component.template))
    component.save()
    expect(component.template.combine_formats).toEqual({
      '1': '{Second} {First}',
    })
  })

  it("updates only exact tokens in the renamed zone's field format", () => {
    const first = { ...zone(), name: 'First [value]' }
    component.template.zones = [first, { ...zone(), name: 'Second' }]
    component.template.combine_formats = {
      '1': 'First [value]: {First [value]} / { First [value] } / {Second} / {First [value] extra}',
      '2': '{First [value]}',
    }

    component.renameZone(first, 'Invoice number')

    expect(first.name).toBe('Invoice number')
    expect(component.template.combine_formats).toEqual({
      '1': 'First [value]: {Invoice number} / {Invoice number} / {Second} / {First [value] extra}',
      '2': '{First [value]}',
    })
  })

  it('keeps tokens in sync when a name is cleared and entered again', () => {
    const first = { ...zone(), name: 'First' }
    component.template.combine_formats = { '1': '{First} - {Second}' }

    component.renameZone(first, '')
    component.renameZone(first, 'Renamed')

    expect(component.getCombineFormat(first)).toBe('{Renamed} - {Second}')
  })

  it('updates built-in field formats and leaves automatic combining implicit', () => {
    const titleZone = {
      ...zone(),
      name: 'First',
      target: 'title' as const,
      custom_field: null,
    }
    component.template.combine_formats = { title: '{First} / {Second}' }

    component.renameZone(titleZone, 'Renamed')
    expect(component.template.combine_formats.title).toBe(
      '{Renamed} / {Second}'
    )

    const customZone = zone()
    component.renameZone(customZone, 'New name')
    expect(component.template.combine_formats['1']).toBeUndefined()
    expect(customZone.name).toBe('New name')
  })

  it('tracks unsaved changes against the initial state', () => {
    fixture.detectChanges()
    expect(component.isDirty).toBe(false)

    component.template.combine_formats = { '1': '' }
    expect(component.isDirty).toBe(false)

    component.template.name = 'Invoices'
    expect(component.isDirty).toBe(true)

    component.template.name = ''
    expect(component.isDirty).toBe(false)

    component.previewDocId = 5
    expect(component.isDirty).toBe(true)
  })

  it('cancels drawing and prevents new gestures or duplicate saves while saving', () => {
    prepareOverlay()
    const pending = new Subject<any>()
    templates.create.mockReturnValue(pending)
    component.onOverlayPointerDown(pointer(500, 500))

    component.save()
    expect(component.saving).toBe(true)
    expect(component.drawingRect()).toBeNull()
    component.save()
    expect(templates.create).toHaveBeenCalledTimes(1)

    component.onOverlayPointerDown(pointer(500, 500))
    component.onOverlayPointerUp(pointer(700, 700))
    expect(component.template.zones).toHaveLength(0)

    const saved = { ...component.template, id: 3 }
    const succeeded = jest.spyOn(component.succeeded, 'emit')
    pending.next(saved)
    pending.complete()
    expect(succeeded).toHaveBeenCalledWith(saved)
    expect(activeModal.close).toHaveBeenCalledWith(saved)
  })

  it('stops an active move and unlocks editing without losing changes after a failed save', () => {
    fixture.detectChanges()
    prepareOverlay()
    component.template.zones = [zone()]
    const pending = new Subject<any>()
    templates.create.mockReturnValue(pending)
    component.onOverlayPointerDown(pointer(150, 150))

    component.save()
    component.onOverlayPointerMove(pointer(250, 250))
    component.onOverlayPointerUp(pointer(250, 250))
    expect(component.template.zones[0].x).toBe(100)

    pending.error(new Error('Save failed'))
    expect(component.saving).toBe(false)
    expect(component.isDirty).toBe(true)
    component.onOverlayPointerDown(pointer(150, 150))
    component.onOverlayPointerUp(pointer(250, 250))
    expect(component.template.zones[0].x).toBe(200)
  })

  it('keeps the language selection reference stable until its value changes', () => {
    const selected = zone()
    selected.ocr_language = 'deu+eng'
    const languages = component.ocrLanguageArray(selected)

    expect(languages).toEqual(['deu', 'eng'])
    expect(component.ocrLanguageArray(selected)).toBe(languages)

    component.setOcrLanguages(selected, ['fra'])
    expect(selected.ocr_language).toBe('fra')
    const updated = component.ocrLanguageArray(selected)
    expect(updated).toEqual(['fra'])
    expect(updated).not.toBe(languages)
    expect(component.ocrLanguageArray(selected)).toBe(updated)

    component.setOcrLanguages(selected, null)
    expect(selected.ocr_language).toBe('')
    const empty = component.ocrLanguageArray(selected)
    expect(empty).toEqual([])
    expect(component.ocrLanguageArray(selected)).toBe(empty)
  })

  it('hides results when extraction settings or geometry change', () => {
    const selected = zone()
    component.template.zones = [selected]
    component.selectedZoneIndex = 0
    component.previewDocId = 1
    templates.testZone.mockReturnValue(of({ value: '123' }))
    component.testZone()
    expect(component.zoneTestResult?.value).toBe('123')

    selected.transform = 'numeric'
    expect(component.zoneTestResult).toBeNull()
    component.testZone()
    selected.width++
    expect(component.zoneTestResult).toBeNull()
  })

  it('cancels a pending test when selection or sample document changes', () => {
    const pending = new Subject<OcrZoneTestResult>()
    component.template.zones = [zone(), zone()]
    component.selectedZoneIndex = 0
    component.previewDocId = 1
    templates.testZone.mockReturnValue(pending)
    component.testZone()
    expect(component.zoneTesting).toBe(true)

    component.selectZone(1)
    pending.next({ value: 'Old zone' })
    expect(component.zoneTesting).toBe(false)
    expect(component.zoneTestResult).toBeNull()

    component.testZone()
    component.clearPreviewDoc()
    pending.next({ value: 'Old document' })
    expect(component.zoneTestResult).toBeNull()
  })

  it('ignores document metadata from a previous preview selection', () => {
    const pending = new Subject<Document>()
    documents.get.mockReturnValueOnce(pending)
    component.previewDocId = 1
    component.loadPreview()
    component.previewDocId = 2
    component.loadPreview()
    pending.next({ id: 1, page_count: 99 } as Document)

    expect(component.previewPageCount).toBe(3)
  })

  it('can retry a failed preview and clear the selected document', () => {
    component.previewDocId = 1
    component.loadPreview()
    component.onImageError()
    expect(component.previewStatus).toBe('error')

    component.loadPreview()
    expect(component.previewStatus).toBe('loading')
    component.clearPreviewDoc()
    expect(component.previewStatus).toBe('empty')
    expect(component.pageImageUrl).toBeNull()
  })
})
