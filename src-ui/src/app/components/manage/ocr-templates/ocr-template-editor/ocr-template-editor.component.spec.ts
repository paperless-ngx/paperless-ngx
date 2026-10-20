import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ElementRef } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbActiveModal, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of, Subject, throwError } from 'rxjs'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { Document } from 'src/app/data/document'
import {
  OcrTemplate,
  OcrTemplateZone,
  OcrZoneTarget,
  OcrZoneTestResult,
  OcrZoneTransform,
} from 'src/app/data/ocr-template'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { OcrTemplateEditorComponent } from './ocr-template-editor.component'

const customFields: CustomField[] = [
  { id: 1, name: 'Invoice number', data_type: CustomFieldDataType.String },
  { id: 2, name: 'Status', data_type: CustomFieldDataType.Select },
]

function zone(overrides: Partial<OcrTemplateZone> = {}): OcrTemplateZone {
  return {
    name: 'Invoice number',
    target: OcrZoneTarget.CustomField,
    custom_field: 1,
    x: 100,
    y: 100,
    width: 200,
    height: 100,
    page: 1,
    ocr_language: 'eng',
    transform: OcrZoneTransform.Strip,
    validation_regex: '',
    order: 0,
    ...overrides,
  }
}

function pointer(x: number, y: number, pointerId = 1): PointerEvent {
  return Object.assign(
    new MouseEvent('pointermove', { clientX: x, clientY: y, button: 0 }),
    { pointerId }
  ) as PointerEvent
}

describe('OcrTemplateEditorComponent', () => {
  let component: OcrTemplateEditorComponent
  let fixture: ComponentFixture<OcrTemplateEditorComponent>
  let documentService: DocumentService
  let templateService: OcrTemplateService
  let modalService: NgbModal
  const activeModal = { close: jest.fn(), dismiss: jest.fn() }

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        OcrTemplateEditorComponent,
      ],
      providers: [
        { provide: NgbActiveModal, useValue: activeModal },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
    jest
      .spyOn(TestBed.inject(CustomFieldsService), 'listAll')
      .mockReturnValue(of({ count: 2, all: [1, 2], results: customFields }))
    jest
      .spyOn(TestBed.inject(DocumentTypeService), 'listAll')
      .mockReturnValue(of({ count: 0, all: [], results: [] }))
    documentService = TestBed.inject(DocumentService)
    jest
      .spyOn(documentService, 'get')
      .mockReturnValue(of({ id: 5, page_count: 3, document_type: 2 }))
    templateService = TestBed.inject(OcrTemplateService)
    modalService = TestBed.inject(NgbModal)
    activeModal.close.mockReset()
    fixture = TestBed.createComponent(OcrTemplateEditorComponent)
    component = fixture.componentInstance
  })

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
    component.pageLoaded.set(true)
  }

  it('should edit a copy of the template and load its sample document', () => {
    const original: OcrTemplate = {
      ...component.template,
      id: 3,
      name: 'Invoices',
      document_type: 1,
      sample_document: 5,
      zones: [zone()],
      combine_formats: { '1': '{Invoice number}' },
    }
    component.object = original
    fixture.detectChanges()

    expect(component.dialogTitle).toEqual('Edit OCR Template')
    expect(component.previewDocId).toEqual(5)
    expect(component.previewPageCount()).toEqual(3)
    expect(component.pageImageUrl).toContain('document-page-image/5/0/')
    expect(component.template.document_type).toEqual(1)
    expect(component.isDirty).toBeFalsy()

    component.template.zones[0].x = 500
    component.template.combine_formats['1'] = 'Edited'
    expect(original.zones[0].x).toEqual(100)
    expect(original.combine_formats['1']).toEqual('{Invoice number}')
  })

  it('should fill the document type from a new sample document', () => {
    component.setSampleDocument([5])
    expect(component.template.document_type).toEqual(2)
  })

  it('should keep only the last picked sample document', () => {
    component.setSampleDocument([5, 6])
    expect(component.sampleDocumentIds).toEqual([6])

    component.setSampleDocument([])
    expect(component.previewDocId).toBeNull()
    expect(component.pageImageUrl).toBeNull()
  })

  it('should ignore a stale sample document response', () => {
    const pending = new Subject<Document>()
    jest.spyOn(documentService, 'get').mockReturnValueOnce(pending)
    component.setSampleDocument([5])
    component.setSampleDocument([6])
    pending.next({ id: 5, page_count: 99 })

    expect(component.previewPageCount()).toEqual(3)
  })

  it('should show a failed page and retry it', () => {
    jest
      .spyOn(documentService, 'get')
      .mockReturnValueOnce(throwError(() => new Error('offline')))
    component.setSampleDocument([5])
    expect(component.pageFailed()).toBeTruthy()

    component.setSampleDocument(component.sampleDocumentIds)
    expect(component.pageFailed()).toBeFalsy()

    component.onImageError()
    expect(component.pageFailed()).toBeTruthy()
  })

  it('should support create and update', () => {
    const createSpy = jest
      .spyOn(templateService, 'create')
      .mockReturnValue(of({ ...component.template, id: 3 }))
    const updateSpy = jest
      .spyOn(templateService, 'update')
      .mockReturnValue(of(component.template))
    const succeededSpy = jest.spyOn(component.succeeded, 'emit')

    component.save()
    expect(createSpy).toHaveBeenCalled()
    expect(succeededSpy).toHaveBeenCalledWith({ ...component.template, id: 3 })
    expect(activeModal.close).toHaveBeenCalled()

    component.saving.set(false)
    component.template.id = 3
    component.save()
    expect(updateSpy).toHaveBeenCalledWith(component.template)
  })

  it('should emit failed and allow editing again after a failed save', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    const pending = new Subject<OcrTemplate>()
    jest.spyOn(templateService, 'create').mockReturnValue(pending)
    const failedSpy = jest.spyOn(component.failed, 'emit')
    component.onOverlayPointerDown(pointer(150, 150))

    component.save()
    component.save()
    expect(templateService.create).toHaveBeenCalledTimes(1)
    component.onOverlayPointerMove(pointer(250, 250))
    component.onOverlayPointerUp(pointer(250, 250))
    expect(component.template.zones[0].x).toEqual(100)

    pending.error(new Error('Save failed'))
    expect(failedSpy).toHaveBeenCalled()
    expect(component.saving()).toBeFalsy()
    component.onOverlayPointerDown(pointer(150, 150))
    component.onOverlayPointerUp(pointer(250, 250))
    expect(component.template.zones[0].x).toEqual(200)
  })

  it('should track unsaved changes', () => {
    fixture.detectChanges()
    expect(component.isDirty).toBeFalsy()

    component.template.combine_formats = { '1': '' }
    expect(component.isDirty).toBeFalsy()

    component.template.name = 'Invoices'
    expect(component.isDirty).toBeTruthy()
    component.template.name = ''
    expect(component.isDirty).toBeFalsy()

    component.setSampleDocument([5])
    expect(component.isDirty).toBeTruthy()
  })

  it('should draw a zone with no field in empty space', () => {
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
    expect(component.selectedZoneIndex).toEqual(0)
  })

  it('should clear the selection on a click in empty space', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    component.selectZone(0)
    component.onOverlayPointerDown(pointer(600, 600))
    component.onOverlayPointerUp(pointer(602, 601))

    expect(component.template.zones).toHaveLength(1)
    expect(component.selectedZoneIndex).toBeNull()
  })

  it('should move a zone when dragging on it', () => {
    prepareOverlay()
    component.template.zones = [zone()]
    component.onOverlayPointerDown(pointer(150, 150))
    component.onOverlayPointerUp(pointer(250, 200))

    expect(component.template.zones).toHaveLength(1)
    expect(component.template.zones[0]).toMatchObject({ x: 200, y: 150 })
  })

  it('should cancel a drawing on escape and ignore other pointers', () => {
    prepareOverlay()
    component.onOverlayPointerDown(pointer(100, 100))
    component.onOverlayPointerUp(pointer(300, 200, 2))
    expect(component.drawingRect()).not.toBeNull()

    component.cancelDrawing()
    component.onOverlayPointerUp(pointer(300, 200))
    expect(component.template.zones).toEqual([])
  })

  it('should open a zone in the zones tab and go back to the list', () => {
    component.template.zones = [zone(), zone()]
    component.selectZone(1)
    expect(component.activeTab).toEqual('zones')
    expect(component.selectedZone).toBe(component.template.zones[1])

    component.deselectZone()
    expect(component.selectedZone).toBeNull()

    component.selectZone(0)
    component.removeZone(0)
    expect(component.template.zones).toHaveLength(1)
    expect(component.selectedZone).toBeNull()
  })

  it('should only offer custom fields OCR can write to', () => {
    fixture.detectChanges()
    expect(component.fieldItems().map((item) => item.id)).toEqual([
      OcrZoneTarget.Title,
      OcrZoneTarget.Asn,
      OcrZoneTarget.Created,
      1,
    ])
  })

  it('should create a custom field and assign it to the zone', () => {
    const succeeded = new Subject<CustomField>()
    const dialog = {
      dialogMode: { set: jest.fn() },
      object: null,
      succeeded,
      failed: new Subject(),
    }
    jest
      .spyOn(modalService, 'open')
      .mockReturnValue({ componentInstance: dialog } as any)
    component.template.zones = [zone({ custom_field: null })]
    component.selectZone(0)

    component.createField()
    expect(dialog.object).toEqual({ name: 'Invoice number' })
    succeeded.next(customFields[0])

    expect(component.template.zones[0].custom_field).toEqual(1)
  })

  it('should build and prune combine formats', () => {
    const first = zone({ name: 'First' })
    const second = zone({ name: 'Second' })
    const other = zone({ name: 'Other', custom_field: 2 })
    component.template.zones = [first, second, other]
    component.template.combine_formats = { '2': '{Other}' }

    expect(component.isFieldShared(first)).toBeTruthy()
    expect(component.isFieldShared(other)).toBeFalsy()
    expect(component.defaultCombineFormat(first)).toEqual('{First} {Second}')

    component.insertCombineToken(first, second)
    component.insertCombineToken(first, first)
    expect(component.getCombineFormat(second)).toEqual('{Second} {First}')

    jest.spyOn(templateService, 'create').mockReturnValue(of(null))
    component.save()
    expect(component.template.combine_formats).toEqual({
      '1': '{Second} {First}',
    })
  })

  it('should update exact tokens when a zone is renamed', () => {
    const first = zone({ name: 'First [value]' })
    component.template.zones = [first, zone({ name: 'Second' })]
    component.template.combine_formats = {
      '1': 'First [value]: {First [value]} / { First [value] } / {Second} / {First [value] extra}',
      '2': '{First [value]}',
    }

    component.renameZone(first, '')
    component.renameZone(first, 'Invoice number')

    expect(first.name).toEqual('Invoice number')
    expect(component.template.combine_formats).toEqual({
      '1': 'First [value]: {Invoice number} / {Invoice number} / {Second} / {First [value] extra}',
      '2': '{First [value]}',
    })
  })

  it('should keep the language array stable until the value changes', () => {
    const selected = zone({ ocr_language: 'deu+eng' })
    const languages = component.ocrLanguageArray(selected)
    expect(languages).toEqual(['deu', 'eng'])
    expect(component.ocrLanguageArray(selected)).toBe(languages)

    component.setOcrLanguages(selected, ['fra'])
    expect(selected.ocr_language).toEqual('fra')
    expect(component.ocrLanguageArray(selected)).toEqual(['fra'])

    component.setOcrLanguages(selected, null)
    expect(component.ocrLanguageArray(selected)).toEqual([])
  })

  it('should hide a test result once the zone changes', () => {
    const selected = zone()
    component.template.zones = [selected]
    component.selectZone(0)
    component.setSampleDocument([5])
    jest
      .spyOn(templateService, 'testZone')
      .mockReturnValue(of({ value: '123' }))

    component.testZone()
    expect(component.zoneTestResult.value).toEqual('123')

    selected.transform = OcrZoneTransform.Numeric
    expect(component.zoneTestResult).toBeNull()
  })

  it('should drop a pending test when the zone or sample document changes', () => {
    const pending = new Subject<OcrZoneTestResult>()
    component.template.zones = [zone(), zone()]
    component.selectZone(0)
    component.setSampleDocument([5])
    jest.spyOn(templateService, 'testZone').mockReturnValue(pending)

    component.testZone()
    expect(component.zoneTesting).toBeTruthy()
    component.selectZone(1)
    pending.next({ value: 'Old zone' })
    expect(component.zoneTestResult).toBeNull()

    component.testZone()
    component.setSampleDocument([])
    pending.next({ value: 'Old document' })
    expect(component.zoneTestResult).toBeNull()
  })
})
